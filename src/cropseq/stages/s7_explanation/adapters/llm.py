"""S7 LLM explainer: ask a model to turn S6 scores into farmer-facing text.

1. Build the system + user message from `prompts.py`.
2. Call the model through LiteLLM (provider chosen by the model string).
3. Parse the JSON reply strictly; a malformed reply raises, so the service can
   fall back to the template instead of shipping broken text.
4. Evidence references are built here from S6 numbers, never from the model.
5. `completer` is injectable so tests run with no network and no API key.
"""

import json
from collections.abc import Callable

from cropseq.config import config
from cropseq.contracts import (
    EvaluatedSequences,
    EvidenceReference,
    Explanation,
)

from ..prompts import SYSTEM_PROMPT, build_user_prompt
from ..select import best_sequence

Completer = Callable[[list[dict[str, str]], str], str]


def _litellm_completer(messages: list[dict[str, str]], model: str) -> str:
    """Default transport. Imported lazily so importing S7 stays cheap."""
    from litellm import completion

    response = completion(
        model=model,
        messages=messages,
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content or ""


class LlmExplainer:
    """Explainer backed by a chat model, with a strict JSON contract."""

    name = "llm"

    def __init__(
        self, model: str | None = None, completer: Completer | None = None
    ) -> None:
        self.model = model or config.llm_model
        self._completer = completer or _litellm_completer

    def explain(self, evaluated: EvaluatedSequences) -> Explanation:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(evaluated)},
        ]
        raw = self._completer(messages, self.model)
        summary, sections = _parse(raw)
        return Explanation(
            summary=summary,
            sections=sections,
            evidence=_evidence(evaluated),
            generated_by="llm",
            warnings=list(evaluated.warnings),
            source=f"S7 LLM explainer ({self.model})",
        )


def _parse(raw: str) -> tuple[str, dict[str, str]]:
    """Accept a JSON object only. Strip accidental code fences."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json")
        text = text.strip()

    data = json.loads(text)
    if not isinstance(data, dict):
        raise TypeError("explainer reply is not a JSON object")

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("explainer reply has no summary")

    raw_sections = data.get("sections", {})
    if not isinstance(raw_sections, dict):
        raise TypeError("explainer sections are not an object")
    sections = {
        str(key): str(value) for key, value in raw_sections.items() if value is not None
    }
    return summary.strip(), sections


def _evidence(evaluated: EvaluatedSequences) -> list[EvidenceReference]:
    """One factual citation to S6, so the text is traceable."""
    if not evaluated.sequences:
        return []
    best = best_sequence(evaluated.sequences)
    return [
        EvidenceReference(
            source_id="ev-001",
            title="S6 evaluation",
            url=None,
            claim=(
                f"{best.sequence_id} is "
                f"{'Pareto-optimal' if best.is_pareto_optimal else 'not Pareto-optimal'} "
                f"with gross_margin={best.metrics['gross_margin']:.2f}, "
                f"water_m3={best.metrics['water_m3']:.2f}, "
                f"soil_score={best.metrics['soil_score']:.4f}."
            ),
        )
    ]
