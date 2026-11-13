"""S8 audit: assemble the final response from the real stage outputs.

1. Accept S7's explanation, S6's evaluation, S1's profile and S3's environment.
2. Standalone: load s7, s6, s3 and s1 fixtures.
3. Choose `recommended_sequence_id` from S6's weighted score (margin as tie-break).
4. Audit the pieces: evidence present, recommended id exists, metrics non-empty.
5. Merge warnings and return a `FinalResponse`. Audit problems are warnings, not errors.

This stage must never replace real inputs with fixture data.
"""

from pathlib import Path

from cropseq.contracts import (
    Environment,
    EvaluatedSequences,
    Explanation,
    FarmerProfile,
    FinalResponse,
)

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S1_OUTPUT = DATA / "s1_output.json"
S3_OUTPUT = DATA / "s3_output.json"
S6_OUTPUT = DATA / "s6_output.json"
S7_OUTPUT = DATA / "s7_output.json"


def _number(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return 0.0


def recommended_sequence_id(evaluated: EvaluatedSequences) -> str | None:
    """Highest weighted score, then highest gross margin."""
    if not evaluated.sequences:
        return None
    best = max(
        evaluated.sequences,
        key=lambda sequence: (
            _number(sequence.notes.get("score")),
            sequence.metrics.get("gross_margin", 0.0),
            sequence.sequence_id,
        ),
    )
    return best.sequence_id


def _audit(
    explanation: Explanation,
    evaluated: EvaluatedSequences,
    recommended: str | None,
) -> list[str]:
    warnings: list[str] = []
    if not explanation.summary.strip():
        warnings.append("Explanation has no summary.")
    if not explanation.evidence:
        warnings.append("Explanation has no evidence references.")
    if recommended is None:
        warnings.append("No sequence could be recommended.")
    elif recommended not in {s.sequence_id for s in evaluated.sequences}:
        warnings.append(f"Recommended sequence {recommended} is not in the results.")
    for sequence in evaluated.sequences:
        if not sequence.metrics:
            warnings.append(f"Sequence {sequence.sequence_id} has no metrics.")
    return warnings


def run(
    explanation: Explanation | None = None,
    evaluated: EvaluatedSequences | None = None,
    profile: FarmerProfile | None = None,
    environment: Environment | None = None,
) -> FinalResponse:
    """Assemble the audited response.

    Standalone: loads s7, s6, s3 and s1 fixtures for the missing inputs.
    """
    if explanation is None:
        explanation = Explanation.model_validate_json(
            S7_OUTPUT.read_text(encoding="utf-8")
        )
    if evaluated is None:
        evaluated = EvaluatedSequences.model_validate_json(
            S6_OUTPUT.read_text(encoding="utf-8")
        )
    if profile is None:
        profile = FarmerProfile.model_validate_json(
            S1_OUTPUT.read_text(encoding="utf-8")
        )
    if environment is None:
        environment = Environment.model_validate_json(
            S3_OUTPUT.read_text(encoding="utf-8")
        )

    recommended = recommended_sequence_id(evaluated)
    warnings: list[str] = []
    for warning in [
        *environment.warnings,
        *evaluated.warnings,
        *explanation.warnings,
        *_audit(explanation, evaluated, recommended),
    ]:
        if warning not in warnings:
            warnings.append(warning)

    return FinalResponse(
        farmer=profile,
        environment=environment,
        evaluated=evaluated,
        explanation=explanation,
        recommended_sequence_id=recommended,
        warnings=warnings,
        source="S8 audit (assembled from stage outputs)",
    )
