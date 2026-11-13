"""S1 tests: the farmer's own profile must survive intake.

1. Every supplied field is echoed unchanged.
2. Empty priorities become equal weights.
3. Land-type casing is normalised by the contract.
4. A standalone run loads the saved fixture.
"""

from pathlib import Path

import pytest

from cropseq.config import config
from cropseq.contracts import FarmerProfile
from cropseq.stages.s1_intake.service import run

DATA = Path(__file__).resolve().parents[2] / "data" / "data_shape"


@pytest.fixture
def profile() -> FarmerProfile:
    return FarmerProfile.model_validate_json(
        (DATA / "s1_input.json").read_text(encoding="utf-8")
    )


def test_profile_is_echoed_not_replaced(profile: FarmerProfile) -> None:
    supplied = profile.model_copy(
        update={
            "farm_id": "farm-xyz",
            "area_ha": 3.5,
            "budget_usd": 1200.0,
            "land_type": "LL",
        }
    )
    result = run(supplied)
    assert result.farm_id == "farm-xyz"
    assert result.area_ha == 3.5
    assert result.budget_usd == 1200.0
    assert result.land_type == "LL"
    assert result.location == supplied.location


def test_empty_priorities_get_equal_weights(profile: FarmerProfile) -> None:
    result = run(profile.model_copy(update={"priorities": {}}))
    assert set(result.priorities) == set(config.objectives)
    assert sum(result.priorities.values()) == pytest.approx(1.0)


def test_given_priorities_are_not_changed(profile: FarmerProfile) -> None:
    priorities = {"gross_margin": 0.9, "water_m3": 0.1}
    result = run(profile.model_copy(update={"priorities": priorities}))
    assert result.priorities == priorities


def test_land_type_is_normalised(profile: FarmerProfile) -> None:
    data = profile.model_dump()
    data["land_type"] = "ll"
    result = run(FarmerProfile.model_validate(data))
    assert result.land_type == "LL"


def test_standalone_loads_fixture() -> None:
    result = run()
    assert result.farm_id
    assert result.area_ha > 0
