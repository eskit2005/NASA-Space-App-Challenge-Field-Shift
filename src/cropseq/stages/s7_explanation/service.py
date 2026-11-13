"""S7 explanation: S6 scores -> farmer-facing explanation.

1. Pick the configured explainer: `llm` (default) or `template`.
2. If the LLM is disabled, or the call or its JSON reply fails, use the template.
3. Never crash the pipeline because of the explainer.
4. Pass S6 warnings through and add our own explanation warnings.
5. Keep the same `Explanation` shape for both adapters.

Standalone: loads s6_output.json.
"""

from pathlib import Path

from cropseq.config import config
from cropseq.contracts import EvaluatedSequences, Explanation

from .adapters.llm import LlmExplainer
from .adapters.template import TemplateExplainer
from .ports import Explainer

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S6_OUTPUT = DATA / "s6_output.json"


def _explainer() -> tuple[Explainer, list[str]]:
    """Return the adapter and any warning about why it was downgraded."""
    name = (config.adapters.get("explainer") or config.adapter_explainer).lower()
    if name == "llm":
        if not config.llm_enabled:
            return TemplateExplainer(), [
                "ADAPTER_EXPLAINER=llm but LLM_ENABLED is false; used template."
            ]
        return LlmExplainer(), []
    if name in {"template", "fake"}:
        return TemplateExplainer(), []

    raise NotImplementedError(
        f"Explainer adapter '{name}' is not implemented. Use 'llm' or 'template' "
        "in ADAPTER_EXPLAINER."
    )


def run(evaluated: EvaluatedSequences | None = None) -> Explanation:
    """Produce the explanation via the configured explainer adapter."""
    if evaluated is None:
        evaluated = EvaluatedSequences.model_validate_json(
            S6_OUTPUT.read_text(encoding="utf-8")
        )

    explainer, warnings = _explainer()
    try:
        explanation = explainer.explain(evaluated)
    except Exception as exc:  # noqa: BLE001 - explanation must never break the run
        warnings.append(
            f"Explainer '{explainer.name}' failed ({type(exc).__name__}); "
            "used template."
        )
        explanation = TemplateExplainer().explain(evaluated)

    if warnings:
        explanation.warnings = [*warnings, *explanation.warnings]
    return explanation
