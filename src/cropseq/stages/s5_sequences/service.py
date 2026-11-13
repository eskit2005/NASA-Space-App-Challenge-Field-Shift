"""S5 sequences: feasible crops -> candidate sequences (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import FeasibleCrops, SequencePool

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S4_OUTPUT = DATA / "s4_output.json"
OUTPUT = DATA / "s5_output.json"


def run(feasible: FeasibleCrops | None = None) -> SequencePool:
    """Build 3-season sequences that pass the rotation rules.

    Standalone: loads s4_output.json. Stub: returns s5_output.json.
    TODO: generate sequences from `feasible`.
    """
    if feasible is None:
        feasible = FeasibleCrops.model_validate_json(
            S4_OUTPUT.read_text(encoding="utf-8")
        )
    return SequencePool.model_validate_json(OUTPUT.read_text(encoding="utf-8"))
