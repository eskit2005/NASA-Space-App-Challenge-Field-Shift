"""S6 scoring: one crop sequence -> three objective metrics.

1. Start from the soil nitrogen stock S3 measured (kg N per ha).
2. For each crop in season order:
   a. Work out irrigation demand from crop water need minus that season's rain.
   b. Give the crop water from the farmer's remaining quota; the share supplied
      sets the water-stress factor `fW`.
   c. Yield `Y = Y_c * N/(N + K_N) * fW`. Climate factor `fC` is 1.0 for now.
   d. Update nitrogen: `N + fertilizer + fixation - uptake - losses`.
   e. Add gross margin: `(price * Y - cost) * area - irrigation cost`.
3. Soil score rewards nitrogen change and penalises nitrogen below a threshold.
   The organic-carbon term is 0.0 because we have no per-crop SOC change data.
4. Flag Pareto-optimal sequences (more margin, less water, better soil).
5. Add a weighted score from the farmer's priorities (reported in `notes`).

All numbers come from `data/crops/crop_params.json` and are placeholders.
No randomness, no I/O.
"""

from dataclasses import dataclass
from typing import Any

from cropseq.contracts import Environment, FarmerProfile

from .params import CropParams, lookup

METRIC_KEYS = ("gross_margin", "water_m3", "soil_score")
_DEFAULT_SEASON = {"precipitation_mm": 0.0}


@dataclass
class ScoredSequence:
    """Internal result before it becomes an `EvaluatedSequence`."""

    sequence_id: str
    crop_ids: list[str]
    metrics: dict[str, float]
    notes: dict[str, str]
    warnings: list[str]


def _number(value: Any, fallback: float) -> float:
    """attributes values can be float | str | bool | None; keep only numbers."""
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    return fallback


def soil_nitrogen_kg_ha(
    environment: Environment, rules: dict[str, Any]
) -> tuple[float, bool]:
    """Total soil N converted to a plant-available stock, kg N per ha.

    Returns (stock, used_fallback). Only a small share of total N is available,
    so `soil_n_available_fraction` scales the measured total.
    """
    attributes = environment.soil.attributes
    total_n = attributes.get("total_nitrogen_g_kg")
    if total_n is None:
        return _number(rules.get("default_n_kg_ha"), 90.0), True

    nitrogen_g_kg = _number(total_n, 0.0)
    if nitrogen_g_kg <= 0:
        return _number(rules.get("default_n_kg_ha"), 90.0), True

    bulk_density = _number(
        attributes.get("bulk_density_kg_dm3"),
        _number(rules.get("bulk_density_default_kg_dm3"), 1.3),
    )
    depth_m = _number(rules.get("root_depth_m"), 0.3)
    available_fraction = _number(rules.get("soil_n_available_fraction"), 0.02)

    stock = nitrogen_g_kg * bulk_density * depth_m * 10000.0 * available_fraction
    return stock, False


def _season_at(environment: Environment, index: int) -> Any:
    if not environment.seasons:
        return _DEFAULT_SEASON
    if index < len(environment.seasons):
        return environment.seasons[index]
    return environment.seasons[-1]


def score_sequence(
    sequence_id: str,
    crop_ids: list[str],
    environment: Environment,
    profile: FarmerProfile,
    catalog: Any,
) -> ScoredSequence:
    """Score one sequence. Missing inputs fall back to defaults with a warning."""
    rules = catalog.rules
    area = profile.area_ha
    remaining_quota = profile.irrigation_quota_m3
    irrigation_cost = _number(rules.get("irrigation_cost_usd_per_m3"), 0.04)
    n_critical = _number(rules.get("n_critical_kg_ha"), 60.0)
    soil_weights = rules.get("soil_weights", {})
    w_nitrogen = _number(soil_weights.get("nitrogen"), 1.0)
    w_carbon = _number(soil_weights.get("organic_carbon"), 0.0)
    w_penalty = _number(soil_weights.get("critical_penalty"), 1.0)

    start_n, used_fallback = soil_nitrogen_kg_ha(environment, rules)
    nitrogen = start_n
    gross_margin = 0.0
    water_demand = 0.0
    water_used = 0.0
    input_cost = 0.0
    fallback_crops: list[str] = []
    rotation_warning = False
    previous_exhaustive = False

    for index, crop_id in enumerate(crop_ids):
        crop, used_defaults = lookup(crop_id, catalog)
        if used_defaults:
            fallback_crops.append(crop_id)
        if previous_exhaustive and crop.exhaustive:
            rotation_warning = True
        previous_exhaustive = crop.exhaustive

        season = _season_at(environment, index)
        rain_mm = _number(getattr(season, "precipitation_mm", None), 0.0)
        demand_m3 = max(0.0, crop.water_mm - rain_mm) * 10.0 * area
        supplied_m3 = min(demand_m3, remaining_quota)
        remaining_quota -= supplied_m3
        water_demand += demand_m3
        water_used += supplied_m3

        supplied_mm = supplied_m3 / (10.0 * area) if area > 0 else 0.0
        if crop.water_mm <= 0:
            water_factor = 1.0
        else:
            water_factor = min(1.0, (rain_mm + supplied_mm) / crop.water_mm)

        yield_t_ha = _yield(crop, nitrogen, water_factor)
        uptake = _uptake(crop, yield_t_ha)
        added = crop.fertilizer_n_kg_ha + crop.n_fixation_kg_ha
        losses = crop.n_loss_fraction * added
        nitrogen = max(0.0, nitrogen + added - uptake - losses)

        crop_cost = crop.cost_usd_per_ha * area
        input_cost += crop_cost + irrigation_cost * supplied_m3
        gross_margin += (
            crop.price_usd_per_t * yield_t_ha - crop.cost_usd_per_ha
        ) * area
        gross_margin -= irrigation_cost * supplied_m3

    soil_score = _soil_score(
        start_n, nitrogen, n_critical, w_nitrogen, w_carbon, w_penalty
    )

    warnings: list[str] = []
    if used_fallback:
        warnings.append(
            "Soil nitrogen missing; S6 used a placeholder stock of "
            f"{start_n:.1f} kg/ha."
        )
    if fallback_crops:
        unique = ", ".join(sorted(set(fallback_crops)))
        warnings.append(f"S6 used placeholder crop defaults for: {unique}.")
    if water_demand > profile.irrigation_quota_m3:
        warnings.append(
            f"Irrigation demand {water_demand:.0f} m3 exceeds the quota "
            f"{profile.irrigation_quota_m3:.0f} m3; yields are water-limited."
        )
    if input_cost > profile.budget_usd:
        warnings.append(
            f"Input cost ${input_cost:.0f} exceeds the budget "
            f"${profile.budget_usd:.0f}."
        )

    notes = {
        "nitrogen_start_kg_ha": f"{start_n:.2f}",
        "nitrogen_end_kg_ha": f"{nitrogen:.2f}",
        "irrigation_demand_m3": f"{water_demand:.2f}",
        "irrigation_used_m3": f"{water_used:.2f}",
        "input_cost_usd": f"{input_cost:.2f}",
        "data_quality": "placeholder",
    }
    if rotation_warning:
        notes["rotation_warning"] = "two exhaustive crops in a row"

    return ScoredSequence(
        sequence_id=sequence_id,
        crop_ids=list(crop_ids),
        metrics={
            "gross_margin": round(gross_margin, 2),
            "water_m3": round(water_demand, 2),
            "soil_score": round(soil_score, 4),
        },
        notes=notes,
        warnings=warnings,
    )


def _yield(crop: CropParams, nitrogen: float, water_factor: float) -> float:
    """Y = Y_c * N/(N + K_N) * fW. fC is not modelled yet."""
    if crop.potential_yield_t_ha <= 0:
        return 0.0
    response = nitrogen / (nitrogen + crop.n_response_kg_ha)
    return crop.potential_yield_t_ha * response * water_factor


def _uptake(crop: CropParams, yield_t_ha: float) -> float:
    """Uptake falls with yield, so a starved crop removes less nitrogen."""
    if crop.potential_yield_t_ha <= 0:
        return 0.0
    return crop.n_uptake_kg_ha * min(1.0, yield_t_ha / crop.potential_yield_t_ha)


def _soil_score(
    start_n: float,
    end_n: float,
    critical_n: float,
    w_nitrogen: float,
    w_carbon: float,
    w_penalty: float,
) -> float:
    """Reward nitrogen gain, penalise falling below the critical stock."""
    relative_n = (end_n - start_n) / start_n if start_n > 0 else 0.0
    relative_carbon = 0.0  # no per-crop SOC change data yet
    shortage = max(0.0, (critical_n - end_n) / critical_n) if critical_n > 0 else 0.0
    raw = w_nitrogen * relative_n + w_carbon * relative_carbon - w_penalty * shortage
    return max(-1.0, min(1.0, raw))


def pareto_flags(rows: list[ScoredSequence]) -> list[bool]:
    """True when no other sequence is at least as good on all three metrics."""
    flags: list[bool] = []
    for i, row in enumerate(rows):
        dominated = False
        for j, other in enumerate(rows):
            if i == j:
                continue
            if _dominates(other.metrics, row.metrics):
                dominated = True
                break
        flags.append(not dominated)
    return flags


def _dominates(better: dict[str, float], worse: dict[str, float]) -> bool:
    """More margin, less water, higher soil score. At least one strictly better."""
    at_least_as_good = (
        better["gross_margin"] >= worse["gross_margin"]
        and better["water_m3"] <= worse["water_m3"]
        and better["soil_score"] >= worse["soil_score"]
    )
    strictly_better = (
        better["gross_margin"] > worse["gross_margin"]
        or better["water_m3"] < worse["water_m3"]
        or better["soil_score"] > worse["soil_score"]
    )
    return at_least_as_good and strictly_better


def weighted_scores(
    rows: list[ScoredSequence], priorities: dict[str, float]
) -> list[float]:
    """Min-max normalise each metric, then weight it with the farmer's priorities."""
    if not rows:
        return []
    weights = {
        key: _number(priorities.get(key), 0.0) if priorities else 0.0
        for key in METRIC_KEYS
    }
    if sum(weights.values()) <= 0:
        weights = {key: 1.0 for key in METRIC_KEYS}

    normalised: dict[str, list[float]] = {}
    for key in METRIC_KEYS:
        values = [row.metrics[key] for row in rows]
        low, high = min(values), max(values)
        if high == low:
            normalised[key] = [0.5 for _ in values]
        elif key == "water_m3":
            normalised[key] = [(high - v) / (high - low) for v in values]
        else:
            normalised[key] = [(v - low) / (high - low) for v in values]

    total_weight = sum(weights.values())
    return [
        sum(weights[key] * normalised[key][i] for key in METRIC_KEYS) / total_weight
        for i in range(len(rows))
    ]
