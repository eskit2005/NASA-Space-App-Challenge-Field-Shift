"""HTTP endpoints. Each route only calls the pipeline or reference data.

1. `/health` is public and cheap, used by the frontend and the host.
2. `/api/v1/intake/message` runs the S0 chat turn.
3. `/api/v1/recommendations/optimize` runs the full pipeline.
4. The two write routes require `X-API-Key` when `API_KEY` is configured.
5. `/api/v1/crops`, `/objectives`, `/seasons` are read-only UI reference data.
"""

from fastapi import APIRouter, Depends

from ..contracts import FarmerProfile, FinalResponse, IntakeReply, IntakeTurn
from ..pipeline import run, run_intake
from . import reference
from .security import require_api_key

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post(
    "/api/v1/intake/message",
    response_model=IntakeReply,
    dependencies=[Depends(require_api_key)],
)
def intake_message(turn: IntakeTurn) -> IntakeReply:
    return run_intake(turn)


@router.post(
    "/api/v1/recommendations/optimize",
    response_model=FinalResponse,
    dependencies=[Depends(require_api_key)],
)
def optimize(profile: FarmerProfile) -> FinalResponse:
    return run(profile)


@router.get("/api/v1/crops")
def list_crops() -> list[dict[str, str]]:
    return reference.crops()


@router.get("/api/v1/objectives")
def list_objectives() -> list[dict[str, str]]:
    return reference.objectives()


@router.get("/api/v1/seasons")
def list_seasons() -> list[dict[str, object]]:
    return reference.seasons()
