"""S5 sequences: feasible crops -> candidate sequences (stub: returns fixture)."""

from pathlib import Path

from cropseq.contracts import FeasibleCrops, SequencePool

FIXTURE = Path(__file__).resolve().parents[4] / "data" / "data_shape" / "s5_output.json"


def run(feasible: FeasibleCrops) -> SequencePool:
    """Build 3-season sequences that pass the rotation rules.

    Stub: returns the s5 fixture. TODO: generate sequences from `feasible`.
    """
    return SequencePool.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
