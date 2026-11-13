"""S3 normalization: raw SoilGrids + weather payloads -> clean `Environment`.

1. `run(profile, raw)` is the only public function of this stage.
2. Convert soil units and apply the farmer's `soil_overrides` (`soil.py`).
3. Aggregate Open-Meteo daily data into the configured seasons (`climate.py`).
4. Estimate the land type and compare it with the farmer's value (`land_type.py`).
5. Collect warnings from every step and from S2. A missing source never crashes
   the run; it only lowers confidence.
6. Return one `Environment` for S4 and S6.
"""

from pathlib import Path

from cropseq.config import config
from cropseq.contracts import Environment, FarmerProfile, RawEnvironment

from .climate import build_season_climate
from .land_type import check_land_type
from .soil import build_soil_profile

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S1_OUTPUT = DATA / "s1_output.json"
S2_OUTPUT = DATA / "s2_output.json"


def run(
    profile: FarmerProfile | None = None,
    raw: RawEnvironment | None = None,
) -> Environment:
    """Normalize raw environmental data and check the farmer's land type.

    Standalone: loads s1_output.json and s2_output.json.
    """
    if profile is None:
        profile = FarmerProfile.model_validate_json(
            S1_OUTPUT.read_text(encoding="utf-8")
        )
    if raw is None:
        raw = RawEnvironment.model_validate_json(S2_OUTPUT.read_text(encoding="utf-8"))

    soil, soil_warnings = build_soil_profile(raw.soil_raw, profile.soil_overrides)
    seasons, climate_warnings = build_season_climate(raw.weather_raw, config.seasons)
    land_type_check, land_type_warnings = check_land_type(
        raw,
        profile.land_type,
        config.land_type_rules,
    )

    warnings = [
        *raw.warnings,
        *soil_warnings,
        *climate_warnings,
        *land_type_warnings,
    ]
    source = f"S3 normalization from RawEnvironment ({raw.source})"

    return Environment(
        location=profile.location,
        soil=soil,
        seasons=seasons,
        land_type_check=land_type_check,
        warnings=warnings,
        source=source,
    )
