"""S7 output and the final pipeline response."""

from .common import EvidenceReference, StageOutput
from .environment import Environment
from .evaluation import EvaluatedSequences
from .farmer import FarmerProfile


class Explanation(StageOutput):
    """Produced by: S7. Consumed by: S8.
    Same shape whether it came from the LLM or the template."""

    summary: str = ""
    # Free-form named parts, e.g. {"rotation_risk": "...", "water": "..."}
    sections: dict[str, str] = {}
    evidence: list[EvidenceReference] = []
    generated_by: str = "template"  # "template" or "llm" (see config.py)


class FinalResponse(StageOutput):
    """Produced by: S8 (audit). Returned by the API / CLI."""

    farmer: FarmerProfile
    environment: Environment
    evaluated: EvaluatedSequences
    explanation: Explanation
