"""S6 optimization: sequences -> scored + Pareto-flagged (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import (
    Environment,
    EvaluatedSequences,
    FarmerProfile,
    SequencePool,
)

FIXTURE = Path(__file__).resolve().parents[4] / "data" / "data_shape" / "s6_output.json"


def run(
    pool: SequencePool,
    environment: Environment,
    profile: FarmerProfile,
) -> EvaluatedSequences:
    """Score every candidate for each configured objective and flag Pareto.

    Stub: returns the s6 fixture. TODO: score `pool` using `environment`,
    `profile.priorities` and config.objectives.
    """
    return EvaluatedSequences.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
