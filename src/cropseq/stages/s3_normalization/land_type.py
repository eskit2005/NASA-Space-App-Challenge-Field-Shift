"""S3 land-type check: estimate the flood class and compare it with the farmer.

1. Build four indicators, each scaled 0 (not flood-prone) to 1 (very flood-prone):
   drainage (SoilGrids clay 15-100 cm), wetness (NASA POWER GWETTOP Jul-Sep),
   monsoon surplus (Open-Meteo rain minus ET, Jun-Oct) and elevation
   (Open-Meteo grid elevation).
2. Combine the available indicators with the weights in `config.land_type_rules`.
   Missing indicators are skipped and the remaining weights are rescaled.
3. Turn the index into HL / MHL / MLL / LL using the configured breaks.
4. Mark confidence high only with enough indicators and enough distance from a
   class boundary.
5. Compare with the farmer's value (match / adjacent / conflict) but never
   replace it. Without a farmer value, use a high-confidence estimate, else MHL.
"""

from __future__ import annotations

from typing import Any

from cropseq.config import LandTypeRules
from cropseq.contracts import LandTypeCheck, RawEnvironment

from .climate import _day_month, _is_number
from .soil import drainage_clay_pct, topsoil_sand_pct

CLASS_ORDER = ["HL", "MHL", "MLL", "LL"]


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def canonical_land_type(value: str) -> str:
    """Map farmer aliases to the four classes used by the rules."""
    clean = value.strip().upper()
    if clean == "ML":
        return "MLL"
    if clean == "VLL":
        return "LL"
    return clean


def drainage_indicator(
    soil_raw: dict[str, Any],
    rules: LandTypeRules,
) -> float | None:
    """More clay in the subsoil means slower drainage and more flood risk."""
    clay = drainage_clay_pct(soil_raw)
    if clay is None:
        return None

    span = rules.clay_max_pct - rules.clay_min_pct
    if span <= 0:
        return None
    score = _clamp((clay - rules.clay_min_pct) / span)

    sand = topsoil_sand_pct(soil_raw)
    if sand is not None and sand >= rules.sandy_topsoil_pct:
        score = max(0.0, score - rules.sandy_penalty)
    return score


def wetness_indicator(
    weather_raw: dict[str, dict],
    rules: LandTypeRules,
) -> float | None:
    """Share of Jul-Sep days with topsoil wetness above the threshold."""
    nasa = weather_raw.get("nasa_power") or {}
    series = nasa.get("properties", {}).get("parameter", {}).get("GWETTOP") or {}
    if not isinstance(series, dict):
        return None

    values: list[float] = []
    for raw_day, raw_value in series.items():
        month = _day_month(
            f"{str(raw_day)[:4]}-{str(raw_day)[4:6]}-{str(raw_day)[6:8]}"
        )
        if month is None or month not in rules.wetness_months:
            continue
        if _is_number(raw_value):
            values.append(float(raw_value))

    if not values:
        return None
    wet_days = sum(1 for value in values if value > rules.wetness_threshold)
    return wet_days / len(values)


def surplus_indicator(
    weather_raw: dict[str, dict],
    rules: LandTypeRules,
) -> float | None:
    """Monsoon rain minus reference ET, divided by the configured divisor."""
    open_meteo = weather_raw.get("open_meteo") or {}
    daily = open_meteo.get("daily") or {}
    times = daily.get("time") or []
    rain = daily.get("precipitation_sum") or []
    et0 = daily.get("et0_fao_evapotranspiration") or []

    total = 0.0
    days = 0
    for index, raw_day in enumerate(times):
        month = _day_month(raw_day)
        if month is None or month not in rules.surplus_months:
            continue
        rain_value = rain[index] if index < len(rain) else None
        et0_value = et0[index] if index < len(et0) else None
        if not _is_number(rain_value) or not _is_number(et0_value):
            continue
        total += float(rain_value) - float(et0_value)
        days += 1

    if days == 0 or rules.surplus_divisor_mm <= 0:
        return None
    return _clamp(total / rules.surplus_divisor_mm)


def elevation_indicator(
    weather_raw: dict[str, dict],
    rules: LandTypeRules,
) -> float | None:
    """Lower ground is more flood-prone. At or below sea level the score is 1."""
    elevation = (weather_raw.get("open_meteo") or {}).get("elevation")
    if not isinstance(elevation, (int, float)) or elevation <= -999:
        return None
    if rules.elevation_datum_m <= 0:
        return None
    return _clamp(
        (rules.elevation_datum_m - float(elevation)) / rules.elevation_datum_m
    )


def build_indicators(
    raw: RawEnvironment,
    rules: LandTypeRules,
) -> dict[str, float | None]:
    """Compute all four indicators. Any unavailable one is None."""
    return {
        "drainage": drainage_indicator(raw.soil_raw, rules),
        "wetness": wetness_indicator(raw.weather_raw, rules),
        "monsoon_surplus": surplus_indicator(raw.weather_raw, rules),
        "elevation": elevation_indicator(raw.weather_raw, rules),
    }


def combine_indicators(
    indicators: dict[str, float | None],
    rules: LandTypeRules,
) -> float | None:
    """Weighted mean over the indicators that exist, rescaled to their weights."""
    numerator = 0.0
    weight_sum = 0.0
    for name, value in indicators.items():
        if value is None:
            continue
        weight = rules.weights.get(name, 0.0)
        if weight <= 0:
            continue
        numerator += weight * value
        weight_sum += weight

    if weight_sum == 0:
        return None
    return numerator / weight_sum


def classify_index(index: float, rules: LandTypeRules) -> str:
    """Turn the 0-1 index into a land-type class."""
    for break_value, class_name in zip(
        rules.class_breaks,
        CLASS_ORDER[: len(rules.class_breaks)],
        strict=False,
    ):
        if index < break_value:
            return class_name
    return CLASS_ORDER[min(len(rules.class_breaks), len(CLASS_ORDER) - 1)]


def assess_confidence(
    index: float | None,
    indicators: dict[str, float | None],
    rules: LandTypeRules,
) -> str:
    """High only when enough indicators exist and the index is clear of a break."""
    available = [value for value in indicators.values() if value is not None]
    if index is None or len(available) < rules.confidence_min_indicators:
        return "low"
    if not rules.class_breaks:
        return "low"
    distance = min(abs(index - break_value) for break_value in rules.class_breaks)
    return "high" if distance >= rules.confidence_margin else "low"


def check_land_type(
    raw: RawEnvironment,
    farmer_land_type: str | None,
    rules: LandTypeRules,
) -> tuple[LandTypeCheck, list[str]]:
    """Estimate the land type, compare it with the farmer, and build the message."""
    warnings: list[str] = []
    indicators = build_indicators(raw, rules)
    index = combine_indicators(indicators, rules)
    estimated = classify_index(index, rules) if index is not None else None
    confidence = assess_confidence(index, indicators, rules)

    if farmer_land_type is None:
        if estimated is not None and confidence == "high":
            used = estimated
            agreement = "not_given"
            message = f"No land type given; using the high-confidence estimate {used}."
        else:
            used = "MHL"
            agreement = "not_given"
            message = (
                "No land type given and the estimate is uncertain; defaulting to "
                "MHL. Please confirm."
            )
            warnings.append(
                "Land type not provided and could not be estimated confidently; "
                "defaulting to MHL"
            )
    else:
        used = canonical_land_type(farmer_land_type)
        if estimated is None:
            agreement = "unknown"
            message = (
                "Could not estimate the land type from the available data; "
                f"using your value {used}."
            )
            warnings.append(f"Land-type check unavailable; using farmer value {used}")
        else:
            difference = abs(CLASS_ORDER.index(used) - CLASS_ORDER.index(estimated))
            if difference == 0:
                agreement = "match"
                message = (
                    f"Your land type {used} matches the soil and weather estimate."
                )
            elif difference == 1:
                agreement = "adjacent"
                message = (
                    f"Your land type {used} is one class away from the estimate "
                    f"{estimated}; using your value."
                )
            else:
                agreement = "conflict"
                message = (
                    f"Your land type {used} conflicts with the "
                    f"{confidence}-confidence estimate {estimated}. Please confirm."
                )
                if confidence == "high":
                    warnings.append(
                        f"Land-type check: estimated {estimated} but farmer "
                        f"reported {used}; please confirm"
                    )

    return (
        LandTypeCheck(
            farmer_land_type=farmer_land_type,
            estimated_land_type=estimated,
            used_land_type=used,
            confidence=confidence,
            agreement=agreement,
            index=round(index, 4) if index is not None else None,
            indicators={
                name: round(value, 4) if value is not None else None
                for name, value in indicators.items()
            },
            message=message,
        ),
        warnings,
    )
