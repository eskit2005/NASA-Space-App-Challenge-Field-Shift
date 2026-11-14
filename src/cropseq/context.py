"""Single-file context store for pipeline runs.

Saves whatever is produced in every stage (mathematical solution, result,
crop list, sequence pool, environment, farmer profile, explanation) into
one single JSON file (`data/pipeline_context.json`).

This file is then passed as context to Stage 0 to answer farmer questions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import config
from .contracts import (
    Environment,
    EvaluatedSequences,
    FarmerProfile,
    FeasibleCrops,
    FinalResponse,
    RawEnvironment,
    SequencePool,
    Explanation,
)

ROOT = Path(__file__).resolve().parents[2]


def get_context_path(file_path: str | Path | None = None) -> Path:
    """Resolve the path to the single pipeline context file."""
    if file_path is not None:
        p = Path(file_path)
    else:
        p = Path(config.pipeline_context_file)
    if not p.is_absolute():
        p = ROOT / p
    return p


def build_summary(
    farmer: dict[str, Any],
    environment: dict[str, Any],
    feasible: dict[str, Any],
    pool: dict[str, Any],
    evaluated: dict[str, Any],
    explanation: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    """Create a structured summary of the pipeline output."""
    sequences = evaluated.get("sequences", [])
    pareto_sequences = [s for s in sequences if s.get("is_pareto_optimal")]
    rec_id = result.get("recommended_sequence_id")
    best_seq = None
    for s in sequences:
        if s.get("sequence_id") == rec_id:
            best_seq = s
            break
    if not best_seq and pareto_sequences:
        best_seq = pareto_sequences[0]

    # Crop list per season
    crops_by_season: dict[str, list[dict[str, str]]] = {}
    for season, crop_objs in feasible.get("by_season", {}).items():
        crops_by_season[season] = [
            {
                "crop_id": c.get("crop_id", ""),
                "name": c.get("name", ""),
                "family": c.get("family", ""),
            }
            for c in crop_objs
            if isinstance(c, dict)
        ]

    soil = environment.get("soil", {})
    return {
        "recommended_sequence_id": rec_id,
        "best_rotation": best_seq,
        "mathematical_solution": {
            "total_sequences_evaluated": len(sequences),
            "pareto_optimal_count": len(pareto_sequences),
            "pareto_sequences": pareto_sequences,
        },
        "crop_list": {
            "by_season": crops_by_season,
            "land_type": feasible.get("land_type", ""),
            "cropping_intensity_k": feasible.get("cropping_intensity_k", 1),
        },
        "sequence_pool": {
            "candidate_count": len(pool.get("sequences", [])),
            "candidates": pool.get("sequences", []),
        },
        "soil_and_climate": {
            "soil_ph": soil.get("ph"),
            "organic_carbon_g_kg": soil.get("organic_carbon_g_kg"),
            "texture": soil.get("texture"),
            "seasons": environment.get("seasons", []),
        },
        "farmer_profile": {
            "farm_id": farmer.get("farm_id"),
            "area_ha": farmer.get("area_ha"),
            "budget_usd": farmer.get("budget_usd"),
            "irrigation_quota_m3": farmer.get("irrigation_quota_m3"),
            "location": farmer.get("location"),
            "attributes": farmer.get("attributes", {}),
        },
        "explanation": {
            "summary": explanation.get("summary", ""),
            "sections": explanation.get("sections", {}),
            "evidence": explanation.get("evidence", []),
        },
    }


def save_pipeline_context(
    farmer: FarmerProfile,
    raw: RawEnvironment,
    environment: Environment,
    feasible: FeasibleCrops,
    pool: SequencePool,
    evaluated: EvaluatedSequences,
    explanation: Explanation,
    result: FinalResponse,
    file_path: str | Path | None = None,
) -> Path:
    """Save whatever got produced in every stage into one single file."""
    path = get_context_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    farmer_dict = farmer.model_dump(mode="json")
    raw_dict = raw.model_dump(mode="json")
    env_dict = environment.model_dump(mode="json")
    feasible_dict = feasible.model_dump(mode="json")
    pool_dict = pool.model_dump(mode="json")
    evaluated_dict = evaluated.model_dump(mode="json")
    explanation_dict = explanation.model_dump(mode="json")
    result_dict = result.model_dump(mode="json")

    summary = build_summary(
        farmer=farmer_dict,
        environment=env_dict,
        feasible=feasible_dict,
        pool=pool_dict,
        evaluated=evaluated_dict,
        explanation=explanation_dict,
        result=result_dict,
    )

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stages": {
            "s1_farmer": farmer_dict,
            "s2_raw_environment": raw_dict,
            "s3_environment": env_dict,
            "s4_feasible_crops": feasible_dict,
            "s5_sequence_pool": pool_dict,
            "s6_mathematical_solution": evaluated_dict,
            "s7_explanation": explanation_dict,
            "s8_final_result": result_dict,
        },
        "summary": summary,
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_pipeline_context(file_path: str | Path | None = None) -> dict[str, Any]:
    """Load the single pipeline context file.

    If not found, builds and saves a baseline context from data/data_shape/ fixtures.
    """
    path = get_context_path(file_path)
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Baseline fallback from data_shape fixtures
    fixtures_dir = ROOT / "data" / "data_shape"
    try:
        farmer_dict = json.loads((fixtures_dir / "s1_output.json").read_text(encoding="utf-8"))
        raw_dict = json.loads((fixtures_dir / "s2_output.json").read_text(encoding="utf-8"))
        env_dict = json.loads((fixtures_dir / "s3_output.json").read_text(encoding="utf-8"))
        feasible_dict = json.loads((fixtures_dir / "s4_output.json").read_text(encoding="utf-8"))
        pool_dict = json.loads((fixtures_dir / "s5_output.json").read_text(encoding="utf-8"))
        evaluated_dict = json.loads((fixtures_dir / "s6_output.json").read_text(encoding="utf-8"))
        explanation_dict = json.loads((fixtures_dir / "s7_output.json").read_text(encoding="utf-8"))
        result_dict = json.loads((fixtures_dir / "s8_output.json").read_text(encoding="utf-8"))
    except Exception:
        return {}

    summary = build_summary(
        farmer=farmer_dict,
        environment=env_dict,
        feasible=feasible_dict,
        pool=pool_dict,
        evaluated=evaluated_dict,
        explanation=explanation_dict,
        result=result_dict,
    )

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stages": {
            "s1_farmer": farmer_dict,
            "s2_raw_environment": raw_dict,
            "s3_environment": env_dict,
            "s4_feasible_crops": feasible_dict,
            "s5_sequence_pool": pool_dict,
            "s6_mathematical_solution": evaluated_dict,
            "s7_explanation": explanation_dict,
            "s8_final_result": result_dict,
        },
        "summary": summary,
    }

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    return data
