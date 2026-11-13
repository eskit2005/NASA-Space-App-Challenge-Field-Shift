"""S1 output / pipeline input: who is asking and what they have.

1. `Location` carries only what S2 needs: latitude and longitude.
2. `FarmerProfile` is the validated request. Every stage downstream reads it.
3. `land_type` is the farmer's monsoon flood-depth class (HL/MHL/MLL/LL/VLL).
   `ML` is accepted and treated as `MLL` by the stages. Default is MHL.
4. `soil_overrides` holds lab-tested values that beat satellite estimates.
5. `attributes` is the escape hatch for extra fields without changing this class.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

LandType = Literal["HL", "MHL", "MLL", "LL", "VLL", "ML"]


class Location(BaseModel):
    """S2 needs ONLY this, not the whole FarmerProfile."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class FarmerProfile(BaseModel):
    """Produced by: S1 (from API/CLI request). Consumed by: S3, S4, S5, S6, S7."""

    farm_id: str
    location: Location
    area_ha: float = Field(gt=0)
    budget_usd: float = Field(ge=0)
    irrigation_quota_m3: float = Field(ge=0)

    # Monsoon flood-depth class. S3 only checks it; S4 uses it.
    land_type: LandType = "MHL"

    # How much the farmer cares about each objective.
    # Keys must match `objectives` in config.py. e.g. {"gross_margin": 0.5, "water_m3": 0.5}
    priorities: dict[str, float] = {}

    # Lab-tested values that override satellite/grid estimates. e.g. {"ph": 6.4}
    soil_overrides: dict[str, float] = {}

    # Anything else a teammate wants to pass in without editing this class.
    attributes: dict[str, float | str] = {}

    @field_validator("land_type", mode="before")
    @classmethod
    def _normalize_land_type(cls, value: object) -> object:
        """Accept lowercase input; the contract stores uppercase codes."""
        if isinstance(value, str):
            return value.strip().upper()
        return value
