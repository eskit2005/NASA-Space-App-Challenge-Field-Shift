"""S7 tests: template text, LLM JSON parsing, and safe fallback.

1. Template adapter is deterministic and leads with the best-scored sequence.
2. LLM adapter parses JSON through an injected fake transport (no network).
3. Bad JSON raises inside the adapter.
4. The service falls back to the template when the model fails or is disabled.
5. An empty evaluation never crashes.
"""

import json
from pathlib import Path

import pytest

from cropseq.config import Config, config
from cropseq.contracts import EvaluatedSequences
from cropseq.stages.s7_explanation import service
from cropseq.stages.s7_explanation.adapters.llm import LlmExplainer
from cropseq.stages.s7_explanation.adapters.template import TemplateExplainer

DATA = Path(__file__).resolve().parents[2] / "data" / "data_shape"


@pytest.fixture
def evaluated() -> EvaluatedSequences:
    return EvaluatedSequences.model_validate_json(
        (DATA / "s6_output.json").read_text(encoding="utf-8")
    )


def _reply(summary: str = "Use seq-002.", sections: dict | None = None) -> str:
    return json.dumps(
        {
            "summary": summary,
            "sections": sections
            if sections is not None
            else {
                "water": "Water is moderate.",
                "soil": "Soil improves.",
                "rotation_risk": "No repeat.",
                "caveat": "Placeholder data.",
            },
        }
    )


def test_default_explainer_is_llm() -> None:
    cfg = Config(_env_file=None)
    assert cfg.adapters["explainer"] == "llm"
    assert cfg.llm_enabled is True


def test_template_leads_with_best_weighted_sequence(
    evaluated: EvaluatedSequences,
) -> None:
    result = TemplateExplainer().explain(evaluated)
    assert result.generated_by == "template"
    # s6_output.json has no weighted score, so margin is the tie-break.
    assert "seq-001" in result.summary
    assert set(result.sections) == {"water", "soil", "rotation_risk", "caveat"}
    assert len(result.evidence) == 1


def test_template_is_deterministic(evaluated: EvaluatedSequences) -> None:
    first = TemplateExplainer().explain(evaluated)
    second = TemplateExplainer().explain(evaluated)
    assert first.model_dump() == second.model_dump()


def test_template_handles_empty_evaluation() -> None:
    result = TemplateExplainer().explain(EvaluatedSequences())
    assert "nothing to recommend" in result.summary
    assert result.evidence == []


def test_llm_adapter_parses_json_without_network(
    evaluated: EvaluatedSequences,
) -> None:
    seen: dict[str, object] = {}

    def completer(messages: list[dict[str, str]], model: str) -> str:
        seen["messages"] = messages
        seen["model"] = model
        return _reply()

    result = LlmExplainer(model="test-model", completer=completer).explain(evaluated)
    assert result.generated_by == "llm"
    assert result.summary == "Use seq-002."
    assert result.sections["water"] == "Water is moderate."
    assert result.evidence
    assert seen["model"] == "test-model"
    messages = seen["messages"]
    assert isinstance(messages, list)
    assert messages[0]["role"] == "system"
    assert "seq-002" in messages[1]["content"]


def test_llm_adapter_rejects_bad_json(evaluated: EvaluatedSequences) -> None:
    explainer = LlmExplainer(completer=lambda messages, model: "not json")
    with pytest.raises(ValueError):
        explainer.explain(evaluated)


def test_llm_adapter_rejects_missing_summary(evaluated: EvaluatedSequences) -> None:
    explainer = LlmExplainer(
        completer=lambda messages, model: json.dumps({"sections": {}})
    )
    with pytest.raises(ValueError):
        explainer.explain(evaluated)


def test_service_falls_back_when_model_fails(
    evaluated: EvaluatedSequences, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(config.adapters, "explainer", "llm")
    monkeypatch.setattr(config, "llm_enabled", True)

    class BoomExplainer:
        name = "llm"

        def explain(self, _evaluated):
            raise RuntimeError("no key")

    monkeypatch.setattr(service, "LlmExplainer", BoomExplainer)
    result = service.run(evaluated)
    assert result.generated_by == "template"
    assert any("failed" in warning for warning in result.warnings)


def test_service_uses_template_when_llm_disabled(
    evaluated: EvaluatedSequences, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(config.adapters, "explainer", "llm")
    monkeypatch.setattr(config, "llm_enabled", False)
    result = service.run(evaluated)
    assert result.generated_by == "template"
    assert any("LLM_ENABLED is false" in warning for warning in result.warnings)
