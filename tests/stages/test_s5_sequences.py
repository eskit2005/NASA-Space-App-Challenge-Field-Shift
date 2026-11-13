"""S5 tests: deterministic sequence generation from seasonal pools.

1. The cartesian product gives one sequence per allowed rotation.
2. Ids and order are stable across runs.
3. Better-suited crops come first.
4. The all-Fallow combination is dropped.
5. An empty pool returns an empty result with a warning, never a crash.
6. `max_sequences` is honoured.
"""

from cropseq.contracts import Crop, FeasibleCrops, SequencePool
from cropseq.stages.s5_sequences.generation import generate_sequences
from cropseq.stages.s5_sequences.service import run


def _crop(crop_id: str, score: float, season: str) -> Crop:
    return Crop(
        crop_id=crop_id,
        name=f"Crop {crop_id}",
        family="Poaceae",
        attributes={
            "suitability_score": score,
            "effective_area_ha": 500.0,
            "season": season,
        },
    )


def _feasible(**pools: list[Crop]) -> FeasibleCrops:
    return FeasibleCrops(
        by_season=pools,
        supported=True,
        land_type="MHL",
        cropping_intensity_k=3,
    )


def test_one_sequence_per_combination() -> None:
    feasible = _feasible(
        Rabi=[_crop("wheat", 0.9, "Rabi"), _crop("potato", 0.8, "Rabi")],
        **{
            "Kharif-1": [_crop("rice", 0.9, "Kharif-1")],
            "Kharif-2": [
                _crop("aman", 0.9, "Kharif-2"),
                _crop("jute", 0.7, "Kharif-2"),
            ],
        },
    )
    sequences = generate_sequences(feasible, max_sequences=60)
    assert len(sequences) == 4
    assert all(len(sequence.crop_ids) == 3 for sequence in sequences)
    assert [sequence.sequence_id for sequence in sequences] == [
        "seq-001",
        "seq-002",
        "seq-003",
        "seq-004",
    ]


def test_best_suited_crop_comes_first() -> None:
    feasible = _feasible(
        Rabi=[_crop("low", 0.1, "Rabi"), _crop("high", 0.9, "Rabi")],
        **{"Kharif-1": [_crop("rice", 0.5, "Kharif-1")], "Kharif-2": []},
    )
    feasible.by_season["Kharif-2"] = [_crop("aman", 0.5, "Kharif-2")]
    sequences = generate_sequences(feasible, max_sequences=60)
    assert sequences[0].crop_ids[0] == "high"


def test_generation_is_deterministic() -> None:
    feasible = _feasible(
        Rabi=[_crop("wheat", 0.9, "Rabi"), _crop("potato", 0.8, "Rabi")],
        **{
            "Kharif-1": [_crop("rice", 0.9, "Kharif-1")],
            "Kharif-2": [_crop("aman", 0.9, "Kharif-2")],
        },
    )
    first = generate_sequences(feasible, max_sequences=60)
    second = generate_sequences(feasible, max_sequences=60)
    assert [s.model_dump() for s in first] == [s.model_dump() for s in second]


def test_all_fallow_is_dropped() -> None:
    feasible = _feasible(
        Rabi=[_crop("999", 0.0, "Rabi")],
        **{
            "Kharif-1": [_crop("999", 0.0, "Kharif-1")],
            "Kharif-2": [_crop("999", 0.0, "Kharif-2")],
        },
    )
    assert generate_sequences(feasible, max_sequences=60) == []


def test_max_sequences_is_honoured() -> None:
    rabi = [_crop(str(i), 0.5, "Rabi") for i in range(10)]
    kharif1 = [_crop(str(10 + i), 0.5, "Kharif-1") for i in range(10)]
    kharif2 = [_crop(str(20 + i), 0.5, "Kharif-2") for i in range(10)]
    feasible = _feasible(Rabi=rabi, **{"Kharif-1": kharif1, "Kharif-2": kharif2})
    assert len(generate_sequences(feasible, max_sequences=7)) == 7


def test_empty_pool_returns_empty_pool_with_warning() -> None:
    feasible = _feasible(Rabi=[], **{"Kharif-1": [], "Kharif-2": []})
    result = run(feasible)
    assert isinstance(result, SequencePool)
    assert result.sequences == []
    assert any("No crop sequence" in warning for warning in result.warnings)


def test_run_on_saved_fixture_uses_real_pools() -> None:
    result = run()
    assert result.sequences
    assert all(len(sequence.crop_ids) == 3 for sequence in result.sequences)
