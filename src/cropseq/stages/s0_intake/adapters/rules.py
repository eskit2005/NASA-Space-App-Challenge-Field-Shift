"""S0 rules adapter: wraps the deterministic extractor in the port shape.

1. Called by default, and whenever the LLM is disabled or fails.
2. Uses the latest farmer message values (see rules.py).
3. Returns no reply text, so service.py uses the canonical question bank.
"""

from cropseq.contracts import FarmerDraft, IntakeMessage

from ..ports import ExtractedTurn
from ..rules import extract_fields


class RulesExtractor:
    """Deterministic adapter used by default and as the LLM fallback."""

    name = "rules"

    def extract(
        self,
        messages: list[IntakeMessage],
        draft: FarmerDraft,
    ) -> ExtractedTurn:
        return ExtractedTurn(fields=extract_fields(messages), reply="")
