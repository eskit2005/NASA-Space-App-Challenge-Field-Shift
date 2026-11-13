"""HTTP endpoints. Each route only calls the pipeline."""

from fastapi import APIRouter

from ..contracts import FarmerProfile, FinalResponse
from ..pipeline import run

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/v1/recommendations/optimize", response_model=FinalResponse)
def optimize(profile: FarmerProfile) -> FinalResponse:
    return run(profile)
