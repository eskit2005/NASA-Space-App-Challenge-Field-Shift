"""S5 sequences: feasible crops -> candidate 3-season sequences.

1. Load the S4 `FeasibleCrops` (or the saved fixture when run standalone).
2. Build sequences with `generation.generate_sequences` (deterministic).
3. Pass S4's warnings through so the reason for an empty pool stays visible.
4. Return a `SequencePool`; S6 scores it.

Nothing is hardcoded: the seasons, the pools and the count come from S4 and config.
"""

from pathlib import Path

from cropseq.config import config
from cropseq.contracts import FeasibleCrops, SequencePool

from .generation import generate_sequences

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S4_OUTPUT = DATA / "s4_output.json"


def run(feasible: FeasibleCrops | None = None) -> SequencePool:
    """Build candidate sequences from the seasonal pools.

    Standalone: loads data/data_shape/s4_output.json.
    """
    if feasible is None:
        feasible = FeasibleCrops.model_validate_json(
            S4_OUTPUT.read_text(encoding="utf-8")
        )

    sequences = generate_sequences(feasible, config.max_sequences)
    warnings = list(feasible.warnings)
    if not sequences:
        warnings.append(
            "No crop sequence could be built from the available seasonal pools."
        )

    return SequencePool(
        sequences=sequences,
        warnings=warnings,
        source=(
            f"S5 sequence generation from {len(feasible.by_season)} seasonal pools"
        ),
    )
