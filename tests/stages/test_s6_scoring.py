"""S6 tests: scoring, nitrogen response, water limits, Pareto and fallbacks.

1. Run the stage standalone on the saved fixtures.
2. Check metric keys, determinism and note types.
3. Check that legumes/rotations change the soil score.
4. Check Pareto flags and that no sequence is dominated.
5. Check that missing data lowers quality but never crashes.
"""

from pathlib import Path

import pytest

from cropseq.config import config
from cropseq.contracts import (
    Environment,
    FarmerProfile,
    SequencePool,
)
from cropseq.stages.s6_optimization.params import (
    load_catalog,
    lookup,
    normalize_crop_id,
)
from cropseq.stages.s6_optimization.service import run

DATA = Path(__file__).resolve().parents[2] / "data" / "data_shape"


@pytest.fixture
def pool() -> SequencePool:
    return SequencePool.model_validate_json(
        (DATA / "s5_output.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def environment() -> Environment:
    return Environment.model_validate_json(
        (DATA / "s3_output.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def profile() -> FarmerProfile:
    return FarmerProfile.model_validate_json(
        (DATA / "s1_output.json").read_text(encoding="utf-8")
    )


def test_run_uses_exactly_the_config_objectives(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    result = run(pool=pool, environment=environment, profile=profile)
    assert result.sequences
    for sequence in result.sequences:
        assert set(sequence.metrics) == set(config.objectives)


def test_run_is_deterministic(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    first = run(pool=pool, environment=environment, profile=profile)
    second = run(pool=pool, environment=environment, profile=profile)
    assert first.model_dump() == second.model_dump()


def test_notes_values_are_strings(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    result = run(pool=pool, environment=environment, profile=profile)
    for sequence in result.sequences:
        assert all(isinstance(value, str) for value in sequence.notes.values())


def test_legume_first_scores_better_soil_than_wheat_after_wheat(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    result = run(pool=pool, environment=environment, profile=profile)
    by_id = {sequence.sequence_id: sequence for sequence in result.sequences}
    assert (
        by_id["seq-002"].metrics["soil_score"] > by_id["seq-003"].metrics["soil_score"]
    )


def test_weakest_sequence_is_not_pareto(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    result = run(pool=pool, environment=environment, profile=profile)
    by_id = {sequence.sequence_id: sequence for sequence in result.sequences}
    assert by_id["seq-003"].is_pareto_optimal is False
    assert any(sequence.is_pareto_optimal for sequence in result.sequences)


def test_placeholder_warning_is_always_emitted(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    result = run(pool=pool, environment=environment, profile=profile)
    assert any("placeholder" in warning.lower() for warning in result.warnings)


def test_missing_soil_nitrogen_falls_back_without_crashing(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    environment = environment.model_copy(deep=True)
    environment.soil.attributes.pop("total_nitrogen_g_kg", None)
    result = run(pool=pool, environment=environment, profile=profile)
    assert result.sequences
    assert any("Soil nitrogen missing" in warning for warning in result.warnings)


def test_unknown_crop_uses_defaults_and_warns(
    environment: Environment, profile: FarmerProfile
) -> None:
    pool = SequencePool(
        sequences=[
            {
                "sequence_id": "seq-unknown",
                "crop_ids": ["dragonfruit", "dragonfruit", "dragonfruit"],
            }
        ]
    )
    result = run(pool=pool, environment=environment, profile=profile)
    assert result.sequences[0].metrics["gross_margin"] > 0
    assert any("dragonfruit" in warning for warning in result.warnings)


def test_no_quota_lowers_margin(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    dry = profile.model_copy(update={"irrigation_quota_m3": 0.0})
    wet = profile.model_copy(update={"irrigation_quota_m3": 1_000_000.0})
    dry_result = run(pool=pool, environment=environment, profile=dry)
    wet_result = run(pool=pool, environment=environment, profile=wet)
    dry_margin = sum(seq.metrics["gross_margin"] for seq in dry_result.sequences)
    wet_margin = sum(seq.metrics["gross_margin"] for seq in wet_result.sequences)
    assert dry_margin < wet_margin


def test_empty_seasons_use_neutral_rainfall(
    pool: SequencePool, environment: Environment, profile: FarmerProfile
) -> None:
    environment = environment.model_copy(update={"seasons": []})
    result = run(pool=pool, environment=environment, profile=profile)
    assert result.sequences


def test_crop_id_lookup_is_name_based() -> None:
    catalog = load_catalog(Path(config.crop_params))
    assert normalize_crop_id(" Mung_Bean ") == "mung bean"
    params, used_defaults = lookup("mung_bean", catalog)
    assert params.is_legume is True
    assert used_defaults is False
