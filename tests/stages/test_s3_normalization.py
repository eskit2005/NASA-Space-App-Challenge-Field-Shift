"""Unit tests for S3 normalization and the land-type check.

1. Build small synthetic SoilGrids / Open-Meteo / NASA payloads (no network).
2. Check unit conversion and farmer overrides.
3. Check each land-type indicator and the weighted index.
4. Check match / adjacent / conflict and the missing-value policies.
5. Check season aggregation, including the year-wrapping Rabi season.
"""

from datetime import date

from cropseq.config import config
from cropseq.contracts import Environment, FarmerProfile, RawEnvironment
from cropseq.stages.s3_normalization.land_type import (
    build_indicators,
    check_land_type,
)
from cropseq.stages.s3_normalization.service import run
from cropseq.stages.s3_normalization.soil import build_soil_profile

DEPTHS = (
    ("0-5cm", 0, 5),
    ("5-15cm", 5, 15),
    ("15-30cm", 15, 30),
    ("30-60cm", 30, 60),
    ("60-100cm", 60, 100),
    ("100-200cm", 100, 200),
)


def _layer(name: str, value: float, d_factor: float) -> dict:
    return {
        "name": name,
        "unit_measure": {"d_factor": d_factor},
        "depths": [
            {
                "label": label,
                "range": {"top_depth": top, "bottom_depth": bottom},
                "values": {"mean": value},
            }
            for label, top, bottom in DEPTHS
        ],
    }


def _soil_raw(
    *,
    clay: float = 300,
    sand: float = 300,
    silt: float = 400,
    ph: float = 65,
    soc: float = 120,
    nitrogen: float = 120,
    include_ph: bool = True,
) -> dict:
    layers = [
        _layer("clay", clay, 10),
        _layer("sand", sand, 10),
        _layer("silt", silt, 10),
        _layer("soc", soc, 10),
        _layer("nitrogen", nitrogen, 100),
        _layer("cec", 180, 10),
        _layer("bdod", 130, 100),
    ]
    if include_ph:
        layers.append(_layer("phh2o", ph, 10))
    return {"properties": {"layers": layers}}


def _open_meteo(
    days: list[tuple[date, float, float, float]],
    elevation: float = 10.0,
) -> dict:
    return {
        "elevation": elevation,
        "daily": {
            "time": [day.isoformat() for day, _, _, _ in days],
            "temperature_2m_mean": [temp for _, temp, _, _ in days],
            "precipitation_sum": [rain for _, _, rain, _ in days],
            "et0_fao_evapotranspiration": [et0 for _, _, _, et0 in days],
        },
    }


def _nasa(wetness: dict[str, float]) -> dict:
    return {"properties": {"parameter": {"GWETTOP": wetness}}}


def _raw(
    soil: dict | None = None,
    open_meteo: dict | None = None,
    nasa: dict | None = None,
) -> RawEnvironment:
    weather: dict[str, dict] = {}
    if open_meteo is not None:
        weather["open_meteo"] = open_meteo
    if nasa is not None:
        weather["nasa_power"] = nasa
    return RawEnvironment(soil_raw=soil or {}, weather_raw=weather)


def _profile(land_type: str = "MHL") -> FarmerProfile:
    return FarmerProfile(
        farm_id="test-farm",
        location={"latitude": 24.78, "longitude": 89.04},
        area_ha=1.0,
        budget_usd=1000.0,
        irrigation_quota_m3=1000.0,
        land_type=land_type,
    )


# ---------------------------------------------------------------------------
# Soil conversion
# ---------------------------------------------------------------------------


def test_soil_units_are_converted() -> None:
    profile, warnings = build_soil_profile(_soil_raw(), {})
    assert profile.ph == 6.5
    assert profile.organic_carbon_g_kg == 12.0
    assert profile.attributes["clay_pct"] == 30.0
    assert profile.attributes["sand_pct"] == 30.0
    assert profile.attributes["total_nitrogen_g_kg"] == 1.2
    assert profile.is_field_tested is False
    assert warnings == []


def test_farmer_ph_override_wins() -> None:
    profile, warnings = build_soil_profile(_soil_raw(ph=50), {"ph": 6.4})
    assert profile.ph == 6.4
    assert profile.is_field_tested is True
    assert any("soil_overrides" in warning for warning in warnings)


def test_missing_soil_ph_is_null_not_guessed() -> None:
    profile, warnings = build_soil_profile(_soil_raw(include_ph=False), {})
    assert profile.ph is None
    assert any("no pH" in warning for warning in warnings)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------


def test_indicators_use_configured_scales() -> None:
    days = [
        (date(2025, 6, 15), 30.0, 600.0, 100.0),
        (date(2025, 7, 15), 30.0, 600.0, 100.0),
        (date(2025, 8, 15), 30.0, 600.0, 100.0),
        (date(2025, 9, 15), 30.0, 600.0, 100.0),
        (date(2025, 10, 15), 30.0, 600.0, 100.0),
    ]
    nasa = _nasa(
        {
            "20250715": 0.9,
            "20250815": 0.9,
            "20250915": 0.9,
            "20250716": 0.5,
            "20250816": 0.5,
            "20250916": 0.5,
        }
    )
    indicators = build_indicators(
        _raw(
            soil=_soil_raw(clay=350, sand=300),
            open_meteo=_open_meteo(days, elevation=5.0),
            nasa=nasa,
        ),
        config.land_type_rules,
    )

    assert indicators["drainage"] == 0.5
    assert indicators["wetness"] == 0.5
    assert indicators["monsoon_surplus"] == 1.0
    assert indicators["elevation"] == 0.75


def test_sandy_topsoil_discounts_drainage() -> None:
    raw = _raw(soil=_soil_raw(clay=350, sand=600))
    indicators = build_indicators(raw, config.land_type_rules)
    assert indicators["drainage"] == 0.2  # 0.5 - 0.3 penalty


def test_missing_sources_lower_confidence_without_crashing() -> None:
    raw = _raw(soil=_soil_raw(clay=340))
    check, warnings = check_land_type(raw, "MHL", config.land_type_rules)

    assert check.indicators["wetness"] is None
    assert check.indicators["monsoon_surplus"] is None
    assert check.indicators["elevation"] is None
    assert check.confidence == "low"
    assert check.estimated_land_type == "MHL"
    assert warnings == []


# ---------------------------------------------------------------------------
# Agreement policy
# ---------------------------------------------------------------------------


def _very_flood_prone_raw() -> RawEnvironment:
    days = [(date(2025, month, 15), 30.0, 1000.0, 100.0) for month in range(6, 11)]
    nasa = _nasa({f"2025{month:02d}15": 0.95 for month in range(7, 10)})
    return _raw(
        soil=_soil_raw(clay=500, sand=300),
        open_meteo=_open_meteo(days, elevation=0.0),
        nasa=nasa,
    )


def test_match_adjacent_conflict_and_warning() -> None:
    raw = _very_flood_prone_raw()
    rules = config.land_type_rules

    match, _ = check_land_type(raw, "LL", rules)
    assert match.estimated_land_type == "LL"
    assert match.agreement == "match"
    assert match.used_land_type == "LL"

    adjacent, _ = check_land_type(raw, "MLL", rules)
    assert adjacent.agreement == "adjacent"

    conflict, warnings = check_land_type(raw, "MHL", rules)
    assert conflict.agreement == "conflict"
    assert conflict.confidence == "high"
    assert conflict.used_land_type == "MHL"  # farmer value is never replaced
    assert any("please confirm" in warning for warning in warnings)


def test_ml_is_treated_as_mll() -> None:
    check, _ = check_land_type(_very_flood_prone_raw(), "ML", config.land_type_rules)
    assert check.farmer_land_type == "ML"
    assert check.used_land_type == "MLL"


def test_missing_land_type_uses_high_estimate_or_defaults_to_mhl() -> None:
    high, _ = check_land_type(_very_flood_prone_raw(), None, config.land_type_rules)
    assert high.confidence == "high"
    assert high.used_land_type == "LL"
    assert high.agreement == "not_given"

    low, warnings = check_land_type(
        _raw(soil=_soil_raw(clay=340)), None, config.land_type_rules
    )
    assert low.confidence == "low"
    assert low.used_land_type == "MHL"
    assert any("defaulting to MHL" in warning for warning in warnings)


# ---------------------------------------------------------------------------
# Season aggregation and the stage entry point
# ---------------------------------------------------------------------------


def test_seasons_aggregate_and_rabi_wraps_the_year() -> None:
    days = [
        (date(2025, 1, 15), 20.0, 10.0, 2.0),
        (date(2025, 11, 15), 22.0, 20.0, 3.0),
        (date(2025, 12, 15), 24.0, 30.0, 4.0),
        (date(2025, 3, 15), 30.0, 40.0, 5.0),
    ]
    environment = run(
        _profile(),
        _raw(soil=_soil_raw(), open_meteo=_open_meteo(days)),
    )

    assert isinstance(environment, Environment)
    assert [season.season for season in environment.seasons] == [
        "Rabi",
        "Kharif-1",
        "Kharif-2",
    ]

    rabi = environment.seasons[0]
    assert rabi.attributes["days"] == 3.0
    assert rabi.mean_temp_c == 22.0
    assert rabi.precipitation_mm == 60.0
    assert rabi.et0_mm == 9.0

    kharif_2 = environment.seasons[2]
    assert kharif_2.attributes["days"] == 0.0
    assert kharif_2.mean_temp_c is None


def test_run_keeps_farmer_value_and_location() -> None:
    environment = run(_profile("HL"), _raw(soil=_soil_raw(clay=500)))
    assert environment.location.latitude == 24.78
    assert environment.land_type_check.farmer_land_type == "HL"
    assert environment.land_type_check.used_land_type == "HL"
