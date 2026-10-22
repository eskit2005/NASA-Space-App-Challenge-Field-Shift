"""S7 explanation: evaluation -> explanation (adapter-driven)."""

from cropseq.config import config
from cropseq.contracts import EvaluatedSequences, Explanation

from .adapters.fake import FakeExplainer
from .ports import Explainer


def _explainer() -> Explainer:
    name = config.adapters["explainer"]
    if name == "fake":
        return FakeExplainer()
    raise NotImplementedError(
        f"Explainer adapter '{name}' is not implemented yet. Create "
        f"'src/cropseq/stages/s7_explanation/adapters/{name}.py' and register "
        "it in _explainer() in src/cropseq/stages/s7_explanation/service.py."
    )


def run(evaluated: EvaluatedSequences) -> Explanation:
    """Produce the explanation via the configured explainer adapter."""
    return _explainer().explain(evaluated)
