"""S5 generation: turn the seasonal crop pools into candidate sequences.

1. Read the pools in season order (Rabi, Kharif-1, Kharif-2).
2. Order each pool by suitability score, then effective area, then crop id.
   That ordering is the only reason one candidate is "first".
3. Take the cartesian product: one crop per season. That is every allowed rotation.
4. Drop duplicates and the all-Fallow sequence.
5. Stop at `max_sequences` so S6 stays fast.
6. Ids are `seq-001`, `seq-002`, ... in generation order, so runs are repeatable.

No randomness. The same pools always give the same sequences.
"""

from itertools import product

from cropseq.contracts import CandidateSequence, Crop, FeasibleCrops

FALLOW_ID = "999"


def _number(crop: Crop, key: str) -> float:
    value = crop.attributes.get(key, 0.0)
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _order_pool(pool: list[Crop]) -> list[Crop]:
    """Best-suited crop first. Ties are broken deterministically."""
    return sorted(
        pool,
        key=lambda crop: (
            -_number(crop, "suitability_score"),
            -_number(crop, "effective_area_ha"),
            crop.crop_id,
        ),
    )


def generate_sequences(
    feasible: FeasibleCrops, max_sequences: int
) -> list[CandidateSequence]:
    """Return up to `max_sequences` rotations, one crop per season."""
    seasons = list(feasible.by_season)
    if not seasons:
        return []

    pools = [feasible.by_season[season] for season in seasons]
    if any(not pool for pool in pools):
        return []

    ordered = [_order_pool(pool) for pool in pools]
    sequences: list[CandidateSequence] = []
    seen: set[tuple[str, ...]] = set()

    for combination in product(*ordered):
        crop_ids = tuple(crop.crop_id for crop in combination)
        if crop_ids in seen:
            continue
        seen.add(crop_ids)
        if all(crop_id == FALLOW_ID for crop_id in crop_ids):
            continue
        sequences.append(
            CandidateSequence(
                sequence_id=f"seq-{len(sequences) + 1:03d}",
                crop_ids=list(crop_ids),
            )
        )
        if len(sequences) >= max_sequences:
            break

    return sequences
