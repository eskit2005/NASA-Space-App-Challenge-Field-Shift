"""S1 intake: validate the request into a FarmerProfile (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import FarmerProfile

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
INPUT = DATA / "s1_input.json"
OUTPUT = DATA / "s1_output.json"


def run(profile: FarmerProfile | None = None) -> FarmerProfile:
    """Validate the incoming profile and apply defaults.

    Standalone: loads s1_input.json. Stub: returns s1_output.json.
    """
    if profile is None:
        profile = FarmerProfile.model_validate_json(INPUT.read_text(encoding="utf-8"))
    return FarmerProfile.model_validate_json(OUTPUT.read_text(encoding="utf-8"))
