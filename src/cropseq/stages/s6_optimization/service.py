"""S6 optimization: sequences -> scored + Pareto-flagged (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import (
    Environment,
    EvaluatedSequences,
    FarmerProfile,
    SequencePool,
)

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S1_OUTPUT = DATA / "s1_output.json"
S3_OUTPUT = DATA / "s3_output.json"
S5_OUTPUT = DATA / "s5_output.json"
OUTPUT = DATA / "s6_output.json"


def run(
    pool: SequencePool | None = None,
    environment: Environment | None = None,
    profile: FarmerProfile | None = None,
) -> EvaluatedSequences:
    """Score every candidate for each configured objective and flag Pareto.

    Standalone: loads s5_output.json, s3_output.json and s1_output.json.
    Stub: returns s6_output.json. TODO: score `pool` using `environment`,
    `profile.priorities` and config.objectives.
    """
    if pool is None:
        pool = SequencePool.model_validate_json(S5_OUTPUT.read_text(encoding="utf-8"))
    if environment is None:
        environment = Environment.model_validate_json(
            S3_OUTPUT.read_text(encoding="utf-8")
        )
    if profile is None:
        profile = FarmerProfile.model_validate_json(
            S1_OUTPUT.read_text(encoding="utf-8")
        )
    return EvaluatedSequences.model_validate_json(OUTPUT.read_text(encoding="utf-8"))
