"""S0 LLM adapter: extract profile fields with a strict JSON prompt.

1. Build the prompt from the whole conversation, the current draft and the
   fields that are still missing.
2. Call LiteLLM (JSON mode) through an injectable `completer`; tests never
   make a real network call.
3. Parse the JSON defensively: strip code fences, keep the first object.
4. Return only the `fields` dict and the optional `reply`.
5. Any failure raises UpstreamUnavailable; service.py falls back to rules.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

from cropseq.config import config
from cropseq.contracts import FarmerDraft, IntakeMessage
from cropseq.errors import UpstreamUnavailable

from ..draft import merge_fields, missing_fields
from ..ports import ExtractedTurn
from ..prompts import SYSTEM_PROMPT, build_user_prompt
from ..rules import extract_fields

Completer = Callable[[str, str], str]


def _parse_json(text: str) -> dict:
    """Parse a JSON object even if the model wrapped it in prose or fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise UpstreamUnavailable("The intake model did not return JSON.")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise UpstreamUnavailable("The intake model returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise UpstreamUnavailable("The intake model returned a non-object JSON value.")
    return data


class LlmExtractor:
    """Chat-model extractor. `completer` is injected in tests."""

    name = "llm"

    def __init__(
        self,
        model: str | None = None,
        completer: Completer | None = None,
    ) -> None:
        self.model = model or config.llm_model
        self._completer = completer

    def _complete(self, system: str, user: str) -> str:
        if self._completer is not None:
            return self._completer(system, user)

        from litellm import completion

        response = completion(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return content or ""

    def extract(
        self,
        messages: list[IntakeMessage],
        draft: FarmerDraft,
    ) -> ExtractedTurn:
        # Rules give a cheap preview, so the model is told what is still
        # missing after the farmer's latest message, not before it.
        preview, _ = merge_fields(draft, extract_fields(messages))
        prompt = build_user_prompt(messages, draft, missing_fields(preview))
        data = _parse_json(self._complete(SYSTEM_PROMPT, prompt))

        fields = data.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        reply = data.get("reply")
        if not isinstance(reply, str):
            reply = ""
        return ExtractedTurn(fields=fields, reply=reply.strip()[:1000])
