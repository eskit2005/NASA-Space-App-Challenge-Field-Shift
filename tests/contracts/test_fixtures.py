"""Every fixture in data/data_shape must validate against its contract,
and the keys they share (objectives, seasons, crop ids) must line up."""

import json
from pathlib import Path

import pytest

from cropseq.config import config
from cropseq.contracts import (
    Environment,
    EvaluatedSequences,
    Explanation,
    FarmerProfile,
    FeasibleCrops,
    FinalResponse,
    RawEnvironment,
    SequencePool,
)

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "data_shape"

OUTPUT_CONTRACTS: dict[str, type] = {
    "s1_output.json": FarmerProfile,
    "s2_output.json": RawEnvironment,
    "s3_output.json": Environment,
    "s4_output.json": FeasibleCrops,
    "s5_output.json": SequencePool,
    "s6_output.json": EvaluatedSequences,
    "s7_output.json": Explanation,
    "s8_output.json": FinalResponse,
}


def load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_fixture_dir_holds_exactly_the_expected_files() -> None:
    expected = {"s1_input.json", *OUTPUT_CONTRACTS}
    assert {p.name for p in FIXTURE_DIR.glob("*.json")} == expected


def test_s1_input_matches_farmer_profile() -> None:
    FarmerProfile.model_validate(load("s1_input.json"))


@pytest.mark.parametrize("name,model", sorted(OUTPUT_CONTRACTS.items()))
def test_output_fixture_matches_contract(name: str, model: type) -> None:
    model.model_validate(load(name))


def test_farmer_priorities_match_config_objectives() -> None:
    farmer = FarmerProfile.model_validate(load("s1_output.json"))
    assert set(farmer.priorities) == set(config.objectives)


def test_season_keys_match_config_seasons() -> None:
    names = [s.name for s in config.seasons]
    environment = Environment.model_validate(load("s3_output.json"))
    assert [c.season for c in environment.seasons] == names
    feasible = FeasibleCrops.model_validate(load("s4_output.json"))
    assert list(feasible.by_season) == names


def test_every_sequence_scored_for_every_objective() -> None:
    evaluated = EvaluatedSequences.model_validate(load("s6_output.json"))
    assert evaluated.sequences
    for seq in evaluated.sequences:
        assert set(seq.metrics) == set(config.objectives)


def test_sequence_crop_ids_are_feasible_in_their_season() -> None:
    feasible = FeasibleCrops.model_validate(load("s4_output.json"))
    pool = SequencePool.model_validate(load("s5_output.json"))
    names = [s.name for s in config.seasons]
    assert pool.sequences
    for seq in pool.sequences:
        assert len(seq.crop_ids) == len(names)
        for season, crop_id in zip(names, seq.crop_ids, strict=True):
            available = [c.crop_id for c in feasible.by_season[season]]
            assert crop_id in available, f"{crop_id} not feasible in {season}"


def test_s6_covers_the_s5_pool() -> None:
    pool = SequencePool.model_validate(load("s5_output.json"))
    evaluated = EvaluatedSequences.model_validate(load("s6_output.json"))
    pool_ids = [(s.sequence_id, s.crop_ids) for s in pool.sequences]
    eval_ids = [(s.sequence_id, s.crop_ids) for s in evaluated.sequences]
    assert eval_ids == pool_ids


def test_final_response_embeds_earlier_outputs() -> None:
    final = FinalResponse.model_validate(load("s8_output.json"))
    assert (
        final.farmer.model_dump()
        == FarmerProfile.model_validate(load("s1_output.json")).model_dump()
    )
    assert (
        final.environment.model_dump()
        == Environment.model_validate(load("s3_output.json")).model_dump()
    )
    assert (
        final.evaluated.model_dump()
        == EvaluatedSequences.model_validate(load("s6_output.json")).model_dump()
    )
    assert (
        final.explanation.model_dump()
        == Explanation.model_validate(load("s7_output.json")).model_dump()
    )
