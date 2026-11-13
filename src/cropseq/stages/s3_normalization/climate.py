"""S3 climate normalization: Open-Meteo daily data -> per-season summaries.

1. Read the daily `time`, `temperature_2m_mean`, `precipitation_sum` and
   `et0_fao_evapotranspiration` arrays.
2. Select the days that fall inside each configured season. A season that wraps
   the year (Rabi, November-February) is handled.
3. Mean the temperature, sum the rain and sum the reference ET.
4. Null days are skipped; a season with no usable days stays `None`.
5. A missing Open-Meteo payload is a warning, never a crash.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from cropseq.contracts import Season, SeasonClimate

FILL_VALUE = -999.0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > FILL_VALUE


def _month_in_season(month: int, start_month: int, end_month: int) -> bool:
    """True if `month` is inside a season, including seasons that wrap the year."""
    if start_month <= end_month:
        return start_month <= month <= end_month
    return month >= start_month or month <= end_month


def _day_month(value: Any) -> int | None:
    """Parse an ISO date string and return its month."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).month
    except ValueError:
        return None


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _sum(values: list[float]) -> float | None:
    return sum(values) if values else None


def build_season_climate(
    weather_raw: dict[str, dict],
    seasons: list[Season],
) -> tuple[list[SeasonClimate], list[str]]:
    """Aggregate Open-Meteo daily values into one `SeasonClimate` per season."""
    open_meteo = weather_raw.get("open_meteo") or {}
    daily = open_meteo.get("daily") or {}
    times = daily.get("time") or []

    if not times:
        warnings = ["Open-Meteo daily data unavailable; season climate left empty"]
        return (
            [
                SeasonClimate(
                    season=season.name,
                    attributes={"days": 0.0, "source": "unavailable"},
                )
                for season in seasons
            ],
            warnings,
        )

    temperatures = daily.get("temperature_2m_mean") or []
    precipitation = daily.get("precipitation_sum") or []
    et0 = daily.get("et0_fao_evapotranspiration") or []

    results: list[SeasonClimate] = []
    warnings: list[str] = []

    for season in seasons:
        temp_values: list[float] = []
        rain_values: list[float] = []
        et0_values: list[float] = []
        days = 0

        for index, raw_day in enumerate(times):
            month = _day_month(raw_day)
            if month is None:
                continue
            if not _month_in_season(month, season.start_month, season.end_month):
                continue

            days += 1
            if index < len(temperatures) and _is_number(temperatures[index]):
                temp_values.append(float(temperatures[index]))
            if index < len(precipitation) and _is_number(precipitation[index]):
                rain_values.append(float(precipitation[index]))
            if index < len(et0) and _is_number(et0[index]):
                et0_values.append(float(et0[index]))

        if days == 0:
            warnings.append(f"No Open-Meteo days inside season {season.name}")

        mean_temp = _mean(temp_values)
        rain_sum = _sum(rain_values)
        et0_sum = _sum(et0_values)

        results.append(
            SeasonClimate(
                season=season.name,
                mean_temp_c=round(mean_temp, 2) if mean_temp is not None else None,
                precipitation_mm=(round(rain_sum, 2) if rain_sum is not None else None),
                et0_mm=round(et0_sum, 2) if et0_sum is not None else None,
                attributes={"days": float(days), "source": "open_meteo"},
            )
        )

    return results, warnings
