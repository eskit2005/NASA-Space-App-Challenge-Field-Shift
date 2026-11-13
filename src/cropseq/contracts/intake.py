"""S0 intake chat: the conversation that fills a FarmerProfile.

1. `IntakeMessage` is one chat line: the farmer or the assistant.
2. `FarmerDraft` is the partially filled profile. Every field is optional
   because the farmer has not answered everything yet.
3. `IntakeTurn` is the stateless request: the whole conversation plus the
   current draft. The frontend resends both on every turn.
4. `IntakeReply` is the answer: the next message, the updated draft, what is
   still missing, and (only when complete) the finished FarmerProfile.
5. `is_complete=True` means the frontend should POST `profile` to the
   existing /api/v1/recommendations/optimize endpoint.
"""

from pydantic import BaseModel, Field

from .common import StageOutput
from .farmer import FarmerProfile, LandType, Location


class IntakeMessage(BaseModel):
    """One chat line. `role` is who said it."""

    role: str = Field(pattern="^(farmer|assistant)$")
    content: str


class FarmerDraft(BaseModel):
    """Partially filled FarmerProfile. Missing fields stay None.

    The rules are the same as FarmerProfile. A value is only stored when the
    farmer actually gave it; the intake stage never guesses.
    """

    location: Location | None = None
    area_ha: float | None = Field(default=None, gt=0)
    budget_usd: float | None = Field(default=None, ge=0)
    irrigation_quota_m3: float | None = Field(default=None, ge=0)
    land_type: LandType | None = None
    priorities: dict[str, float] = {}
    soil_overrides: dict[str, float] = {}
    attributes: dict[str, float | str] = {}


class IntakeTurn(BaseModel):
    """Stateless S0 input. `draft` is whatever was collected so far."""

    messages: list[IntakeMessage] = []
    draft: FarmerDraft = Field(default_factory=FarmerDraft)
    # Generated once by the frontend. If absent, S0 derives a stable id.
    farm_id: str | None = None


class IntakeReply(StageOutput):
    """S0 output: the next chat message plus the updated draft."""

    reply: str
    draft: FarmerDraft = Field(default_factory=FarmerDraft)
    missing_fields: list[str] = []
    is_complete: bool = False
    # Exact JSON to send to the optimize endpoint. None until complete.
    profile: FarmerProfile | None = None
