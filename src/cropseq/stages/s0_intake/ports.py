"""Ports (Protocol interfaces) for S0. Adapters implement these.

1. An adapter receives the whole conversation and the current draft.
2. It returns only the fields the farmer actually stated, plus an optional
   reply text.
3. It never decides that the profile is complete; service.py does that.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

from cropseq.contracts import FarmerDraft, IntakeMessage


@dataclass
class ExtractedTurn:
    """What an adapter found in the conversation."""

    fields: dict[str, Any] = field(default_factory=dict)
    reply: str = ""


class IntakeExtractor(Protocol):
    """Turns farmer messages into profile fields."""

    name: str

    def extract(
        self,
        messages: list[IntakeMessage],
        draft: FarmerDraft,
    ) -> ExtractedTurn: ...
