"""S7 explanation: evaluation -> explanation (adapter-driven)."""

from pathlib import Path

from cropseq.config import config
from cropseq.contracts import EvaluatedSequences, Explanation

from .adapters.fake import FakeExplainer
from .ports import Explainer

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S6_OUTPUT = DATA / "s6_output.json"


def _explainer() -> Explainer:
    name = config.adapters["explainer"]
    if name == "fake":
        return FakeExplainer()
    raise NotImplementedError(
        f"Explainer adapter '{name}' is not implemented yet. Create "
        f"'src/cropseq/stages/s7_explanation/adapters/{name}.py' and register "
        "it in _explainer() in src/cropseq/stages/s7_explanation/service.py."
    )


def run(evaluated: EvaluatedSequences | None = None) -> Explanation:
    """Produce the explanation via the configured explainer adapter.

    Standalone: loads s6_output.json.
    """
    if evaluated is None:
        evaluated = EvaluatedSequences.model_validate_json(
            S6_OUTPUT.read_text(encoding="utf-8")
        )
    return _explainer().explain(evaluated)
