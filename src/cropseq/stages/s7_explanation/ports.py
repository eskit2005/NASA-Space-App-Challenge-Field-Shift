"""Ports (Protocol interfaces) for S7. Adapters implement these."""

from typing import Protocol

from cropseq.contracts import EvaluatedSequences, Explanation


class Explainer(Protocol):
    """Turns evaluation results into a user-facing explanation."""

    def explain(self, evaluated: EvaluatedSequences) -> Explanation: ...
