"""Working fake adapter for S7: the explanation comes from the stage fixture."""

from cropseq.contracts import EvaluatedSequences, Explanation

from ..fixture import load_fixture


class FakeExplainer:
    """Deterministic explainer: returns the Explanation stored in s7_output.json."""

    def explain(self, evaluated: EvaluatedSequences) -> Explanation:
        # TODO: build sections from `evaluated` once the real template exists.
        return Explanation.model_validate(load_fixture())
