"""S7 selection: which sequence the explanation should lead with.

1. Use S6's weighted `notes.score` when present.
2. Fall back to gross margin, then sequence id, so the choice is deterministic.
3. `crops_text` renders the rotation the same way in the template and LLM paths.
"""

import math

from cropseq.contracts import EvaluatedSequence


def best_sequence(sequences: list[EvaluatedSequence]) -> EvaluatedSequence:
    """Highest weighted score; margin breaks ties; id breaks the rest."""

    def key(sequence: EvaluatedSequence) -> tuple[float, float, str]:
        try:
            score = float(sequence.notes.get("score", "nan"))
        except ValueError:
            score = float("nan")
        if math.isnan(score):
            score = 0.0
        return (score, sequence.metrics["gross_margin"], sequence.sequence_id)

    return max(sequences, key=key)


def crops_text(sequence: EvaluatedSequence) -> str:
    """'wheat -> rice -> mung_bean'"""
    return " -> ".join(sequence.crop_ids)
