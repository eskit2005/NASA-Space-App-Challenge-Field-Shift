"""S2 and S3 outputs. Kept separate on purpose:
S2 only FETCHES (raw, untouched). S3 only CONVERTS (units, aggregation).

1. `RawEnvironment` is what S2 returns: untouched API payloads, cached.
2. `SoilProfile` holds clean soil values in standard units.
3. `SeasonClimate` holds one season's summary. Values are optional because a
   missing source must lower confidence, not crash the run.
4. `LandTypeCheck` records the land type the farmer gave, the estimate made
   from soil/weather, how they compare, and the one-line message for the user.
5. `Environment` is what S3 returns and S4/S6 consume.
"""

from typing import Literal

from pydantic import BaseModel

from .common import StageOutput
from .farmer import Location


class RawEnvironment(StageOutput):
    """Produced by: S2. Consumed by: S3.  Data exactly as the API returned it."""

    soil_raw: dict = {}  # e.g. SoilGrids JSON, pH still as 65 not 6.5
    # One raw payload per weather provider, keyed by adapter name.
    # e.g. {"open_meteo": {...}, "nasa_power": {...}}
    weather_raw: dict[str, dict] = {}
    fetched_at: str = ""  # ISO timestamp


class SoilProfile(BaseModel):
    """Clean soil values in standard units."""

    ph: float | None = None
    organic_carbon_g_kg: float | None = None
    texture: str | None = None  # e.g. "loam"
    is_field_tested: bool = False  # True if it came from farmer_overrides
    attributes: dict[str, float | str] = {}  # extra soil values (clay %, N, ...)


class SeasonClimate(BaseModel):
    """Climate summary for one season. None means the source had no usable data."""

    season: str  # matches Season.name
    mean_temp_c: float | None = None
    precipitation_mm: float | None = None
    et0_mm: float | None = None  # reference evapotranspiration
    attributes: dict[str, float | str] = {}


class LandTypeCheck(BaseModel):
    """S3's cross-check of the farmer's land type against soil and weather.

    The farmer value is never replaced. `used_land_type` is what S4 should use:
    the farmer value when given, otherwise a high-confidence estimate or MHL.
    """

    farmer_land_type: str | None = None
    estimated_land_type: str | None = None
    used_land_type: str = "MHL"
    confidence: Literal["high", "low"] = "low"
    agreement: Literal["match", "adjacent", "conflict", "not_given", "unknown"] = (
        "not_given"
    )
    index: float | None = None  # 0 = not flood-prone, 1 = very flood-prone
    indicators: dict[str, float | None] = {}
    message: str = ""


class Environment(StageOutput):
    """Produced by: S3. Consumed by: S4, S6."""

    location: Location
    soil: SoilProfile
    seasons: list[SeasonClimate]
    land_type_check: LandTypeCheck
