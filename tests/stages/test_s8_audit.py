"""S8 tests: assemble the response from real inputs, never from fixtures.

1. The farmer profile and environment passed in are the ones returned.
2. `recommended_sequence_id` is the best weighted sequence.
3. Warnings from earlier stages are merged and de-duplicated.
4. An empty evaluation returns no recommendation and a warning.
"""

from pathlib import Path

import pytest

from cropseq.contracts import (
    Environment,
    EvaluatedSequences,
    FarmerProfile,
)
from cropseq.stages.s6_optimization.service import run as s6_run
from cropseq.stages.s7_explanation.adapters.template import TemplateExplainer
from cropseq.stages.s8_audit.service import run

DATA = Path(__file__).resolve().parents[2] / "data" / "data_shape"


@pytest.fixture
def profile() -> FarmerProfile:
    return FarmerProfile.model_validate_json(
        (DATA / "s1_input.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def environment() -> Environment:
    return Environment.model_validate_json(
        (DATA / "s3_output.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def evaluated() -> EvaluatedSequences:
    return s6_run()


def test_real_inputs_are_returned_unchanged(
    profile: FarmerProfile,
    environment: Environment,
    evaluated: EvaluatedSequences,
) -> None:
    supplied = profile.model_copy(update={"farm_id": "farm-xyz", "area_ha": 2.0})
    result = run(
        explanation=TemplateExplainer().explain(evaluated),
        evaluated=evaluated,
        profile=supplied,
        environment=environment,
    )
    assert result.farmer.farm_id == "farm-xyz"
    assert result.farmer.area_ha == 2.0
    assert result.environment == environment


def test_recommends_the_best_weighted_sequence(
    profile: FarmerProfile,
    environment: Environment,
    evaluated: EvaluatedSequences,
) -> None:
    result = run(
        explanation=TemplateExplainer().explain(evaluated),
        evaluated=evaluated,
        profile=profile,
        environment=environment,
    )
    assert result.recommended_sequence_id == "seq-002"
    assert result.recommended_sequence_id in {
        sequence.sequence_id for sequence in result.evaluated.sequences
    }


def test_warnings_are_merged_without_duplicates(
    profile: FarmerProfile,
    environment: Environment,
    evaluated: EvaluatedSequences,
) -> None:
    result = run(
        explanation=TemplateExplainer().explain(evaluated),
        evaluated=evaluated,
        profile=profile,
        environment=environment,
    )
    assert len(result.warnings) == len(set(result.warnings))
    assert any("placeholder" in warning.lower() for warning in result.warnings)


def test_empty_evaluation_returns_no_recommendation(
    profile: FarmerProfile, environment: Environment
) -> None:
    empty = EvaluatedSequences()
    result = run(
        explanation=TemplateExplainer().explain(empty),
        evaluated=empty,
        profile=profile,
        environment=environment,
    )
    assert result.recommended_sequence_id is None
    assert any("No sequence could be recommended" in w for w in result.warnings)


def test_standalone_loads_fixtures() -> None:
    result = run()
    assert result.farmer.farm_id
    assert result.recommended_sequence_id
