"""S3 normalization: raw payloads -> clean Environment (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import Environment, FarmerProfile, RawEnvironment

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S1_OUTPUT = DATA / "s1_output.json"
S2_OUTPUT = DATA / "s2_output.json"
OUTPUT = DATA / "s3_output.json"


def run(
    profile: FarmerProfile | None = None,
    raw: RawEnvironment | None = None,
) -> Environment:
    """Convert units and aggregate per season.

    Standalone: loads s1_output.json and s2_output.json.
    Stub: returns s3_output.json. TODO: derive this from `raw`
    (e.g. SoilGrids pH x10 -> pH) using `profile.soil_overrides`.
    """
    if profile is None:
        profile = FarmerProfile.model_validate_json(
            S1_OUTPUT.read_text(encoding="utf-8")
        )
    if raw is None:
        raw = RawEnvironment.model_validate_json(S2_OUTPUT.read_text(encoding="utf-8"))
    return Environment.model_validate_json(OUTPUT.read_text(encoding="utf-8"))
