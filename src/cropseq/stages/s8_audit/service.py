"""S8 audit: assemble + sanity-check the final response (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import EvaluatedSequences, Explanation, FinalResponse

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S6_OUTPUT = DATA / "s6_output.json"
S7_OUTPUT = DATA / "s7_output.json"
OUTPUT = DATA / "s8_output.json"


def run(
    explanation: Explanation | None = None,
    evaluated: EvaluatedSequences | None = None,
) -> FinalResponse:
    """Assemble the response and audit evidence/metrics consistency.

    Standalone: loads s7_output.json and s6_output.json.
    Stub: returns s8_output.json. TODO: audit `explanation.evidence`
    against `evaluated` and assemble the response from the inputs.
    """
    if explanation is None:
        explanation = Explanation.model_validate_json(
            S7_OUTPUT.read_text(encoding="utf-8")
        )
    if evaluated is None:
        evaluated = EvaluatedSequences.model_validate_json(
            S6_OUTPUT.read_text(encoding="utf-8")
        )
    return FinalResponse.model_validate_json(OUTPUT.read_text(encoding="utf-8"))
