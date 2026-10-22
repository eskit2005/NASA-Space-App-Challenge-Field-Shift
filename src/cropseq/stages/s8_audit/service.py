"""S8 audit: assemble + sanity-check the final response (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import EvaluatedSequences, Explanation, FinalResponse

FIXTURE = Path(__file__).resolve().parents[4] / "data" / "data_shape" / "s8_output.json"


def run(explanation: Explanation, evaluated: EvaluatedSequences) -> FinalResponse:
    """Assemble the response and audit evidence/metrics consistency.

    Stub: returns the s8 fixture. TODO: audit `explanation.evidence`
    against `evaluated` and assemble the response from the inputs.
    """
    return FinalResponse.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
