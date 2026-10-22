"""S1 output / pipeline input: who is asking and what they have."""

from pydantic import BaseModel, Field


class Location(BaseModel):
    """S2 needs ONLY this, not the whole FarmerProfile."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class FarmerProfile(BaseModel):
    """Produced by: S1 (from API/CLI request). Consumed by: S4, S5, S6, S7."""

    farm_id: str
    location: Location
    area_ha: float = Field(gt=0)
    budget_usd: float = Field(ge=0)
    irrigation_quota_m3: float = Field(ge=0)

    # How much the farmer cares about each objective.
    # Keys must match `objectives` in config.py. e.g. {"gross_margin": 0.5, "water_m3": 0.5}
    priorities: dict[str, float] = {}

    # Lab-tested values that override satellite/grid estimates. e.g. {"ph": 6.4}
    soil_overrides: dict[str, float] = {}

    # Anything else a teammate wants to pass in without editing this class.
    attributes: dict[str, float | str] = {}
