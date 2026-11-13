"""S6 parameters: load the mock crop table and look up one crop.

1. Read `data/crops/crop_params.json` once per run.
2. Normalise crop ids so `Mung Bean`, `mung_bean` and `mung bean` match.
3. Return explicit crop values when present, otherwise the shared defaults.
4. Track which crops fell back to defaults so S6 can warn the user.

Every number in this file is a mock (see `_meta.is_placeholder`).
"""

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CropParams:
    """One crop's mock traits. Units are documented in the JSON `_meta`."""

    potential_yield_t_ha: float
    price_usd_per_t: float
    cost_usd_per_ha: float
    water_mm: float
    n_uptake_kg_ha: float
    n_fixation_kg_ha: float
    fertilizer_n_kg_ha: float
    n_loss_fraction: float
    n_response_kg_ha: float
    is_legume: bool
    exhaustive: bool


@dataclass(frozen=True)
class Catalog:
    """The whole mock table: defaults, per-crop overrides and shared rules."""

    defaults: CropParams
    crops: dict[str, CropParams]
    rules: dict[str, Any]
    is_placeholder: bool


def normalize_crop_id(value: str) -> str:
    """`Mung_Bean` -> `mung bean`. Crop ids and names share one namespace."""
    cleaned = value.strip().lower().replace("_", " ").replace("-", " ")
    return " ".join(cleaned.split())


def _params_from(raw: dict[str, Any], defaults: dict[str, Any]) -> CropParams:
    merged = {**defaults, **raw}
    allowed = {f.name for f in fields(CropParams)}
    return CropParams(**{k: merged[k] for k in allowed if k in merged})


def load_catalog(path: Path) -> Catalog:
    """Read the JSON table. Raises if the file is missing or malformed."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    crops = {
        normalize_crop_id(name): _params_from(values, defaults)
        for name, values in raw.get("crops", {}).items()
    }
    return Catalog(
        defaults=_params_from({}, defaults),
        crops=crops,
        rules=raw.get("_meta", {}).get("rules", {}),
        is_placeholder=bool(raw.get("_meta", {}).get("is_placeholder", False)),
    )


def lookup(crop_id: str, catalog: Catalog) -> tuple[CropParams, bool]:
    """Return the crop's mock traits and whether the defaults were used."""
    found = catalog.crops.get(normalize_crop_id(crop_id))
    if found is None:
        return catalog.defaults, True
    return found, False
