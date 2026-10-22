"""S2 and S3 outputs. Kept separate on purpose:
S2 only FETCHES (raw, untouched). S3 only CONVERTS (units, aggregation).
Cache the raw one, so changing S3 logic never needs a refetch."""

from pydantic import BaseModel

from .common import StageOutput


class RawEnvironment(StageOutput):
    """Produced by: S2. Consumed by: S3.  Data exactly as the API returned it."""

    soil_raw: dict = {}  # e.g. SoilGrids JSON, pH still as 65 not 6.5
    weather_raw: dict = {}  # e.g. Open-Meteo daily JSON
    fetched_at: str = ""  # ISO timestamp


class SoilProfile(BaseModel):
    """Clean soil values in standard units."""

    ph: float
    organic_carbon_g_kg: float | None = None
    texture: str | None = None  # e.g. "loam"
    is_field_tested: bool = False  # True if it came from farmer_overrides
    attributes: dict[str, float | str] = {}  # extra soil values (clay %, N, ...)


class SeasonClimate(BaseModel):
    """Climate summary for one season."""

    season: str  # matches Season.name
    mean_temp_c: float
    precipitation_mm: float
    et0_mm: float  # reference evapotranspiration
    attributes: dict[str, float | str] = {}


class Environment(StageOutput):
    """Produced by: S3. Consumed by: S4, S6."""

    soil: SoilProfile
    seasons: list[SeasonClimate]
