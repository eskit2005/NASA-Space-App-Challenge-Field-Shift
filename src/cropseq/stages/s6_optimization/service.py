"""S6 optimization: sequence pool -> scored, Pareto-flagged sequences.

1. Load the mock crop table (every number is a placeholder).
2. Score each sequence with `engine.score_sequence` (nitrogen, water, yield, money).
3. Flag sequences that no other sequence beats on all three objectives.
4. Add a weighted score from the farmer's priorities to `notes`.
5. Keep the metric keys equal to `config.objectives` so the pipeline check passes.
6. Deny nothing silently: collect per-sequence warnings into one list.

Standalone: loads s5_output.json, s3_output.json and s1_output.json.
"""

from pathlib import Path

from cropseq.config import config
from cropseq.contracts import (
    Environment,
    EvaluatedSequence,
    EvaluatedSequences,
    FarmerProfile,
    SequencePool,
)

from .engine import pareto_flags, score_sequence, weighted_scores
from .params import load_catalog

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S1_OUTPUT = DATA / "s1_output.json"
S3_OUTPUT = DATA / "s3_output.json"
S5_OUTPUT = DATA / "s5_output.json"


def run(
    pool: SequencePool | None = None,
    environment: Environment | None = None,
    profile: FarmerProfile | None = None,
) -> EvaluatedSequences:
    """Score every candidate for each configured objective and flag Pareto."""
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

    catalog = load_catalog(Path(config.crop_params))
    warnings: list[str] = []
    if catalog.is_placeholder:
        warnings.append(
            "S6 crop parameters are placeholders (data/crops/crop_params.json); "
            "scores are not agronomic advice."
        )

    rows = [
        score_sequence(seq.sequence_id, seq.crop_ids, environment, profile, catalog)
        for seq in pool.sequences
    ]
    flags = pareto_flags(rows)
    scores = weighted_scores(rows, profile.priorities)

    sequences: list[EvaluatedSequence] = []
    for row, is_optimal, score in zip(rows, flags, scores, strict=True):
        notes = dict(row.notes)
        notes["score"] = f"{score:.4f}"
        sequences.append(
            EvaluatedSequence(
                sequence_id=row.sequence_id,
                crop_ids=row.crop_ids,
                metrics=row.metrics,
                is_pareto_optimal=is_optimal,
                notes=notes,
            )
        )
        for warning in row.warnings:
            if warning not in warnings:
                warnings.append(warning)

    return EvaluatedSequences(
        sequences=sequences,
        warnings=warnings,
        source="S6 optimization (placeholder crop parameters)",
    )
