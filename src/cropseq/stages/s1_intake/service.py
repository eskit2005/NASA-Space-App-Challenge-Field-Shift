"""S1 intake: validate the request into a FarmerProfile (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import FarmerProfile

FIXTURE = Path(__file__).resolve().parents[4] / "data" / "data_shape" / "s1_output.json"


def run(profile: FarmerProfile) -> FarmerProfile:
    """Validate the incoming profile and apply defaults.

    Stub: returns the s1 fixture. TODO: merge `profile` with defaults instead.
    """
    return FarmerProfile.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
