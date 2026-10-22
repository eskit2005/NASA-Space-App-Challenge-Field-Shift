"""S3 normalization: raw payloads -> clean Environment (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import Environment, FarmerProfile, RawEnvironment

FIXTURE = Path(__file__).resolve().parents[4] / "data" / "data_shape" / "s3_output.json"


def run(profile: FarmerProfile, raw: RawEnvironment) -> Environment:
    """Convert units and aggregate per season.

    Stub: returns the s3 fixture. TODO: derive this from `raw`
    (e.g. SoilGrids pH x10 -> pH) using `profile.soil_overrides`.
    """
    return Environment.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
