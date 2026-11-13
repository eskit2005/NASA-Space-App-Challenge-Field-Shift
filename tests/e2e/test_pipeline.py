"""End-to-end test for full pipeline with live S2 providers."""

import json
import os
from pathlib import Path

import pytest

from cropseq.contracts import FarmerProfile, FinalResponse
from cropseq.pipeline import run

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "data" / "data_shape"


@pytest.mark.skipif(
    not os.getenv("CROPSEQ_LIVE"), reason="requires live SoilGrids/Open-Meteo"
)
def test_pipeline_run_e2e() -> None:
    input_data = json.loads((FIXTURE_DIR / "s1_input.json").read_text(encoding="utf-8"))
    profile = FarmerProfile.model_validate(input_data)

    response = run(profile)
    assert isinstance(response, FinalResponse)
    assert response.farmer.farm_id == profile.farm_id
    assert response.environment.soil
    assert response.evaluated.sequences
    assert response.explanation.summary
    assert response.environment.seasons
