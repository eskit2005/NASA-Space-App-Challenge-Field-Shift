"""Read-only reference data for the frontend.

1. `crops()` lists every crop in the BARC database, with its botanical family
   from the local taxonomy file. It lets the UI show names instead of ids.
2. `objectives()` lists the scoring keys with farmer-facing labels and units.
3. `seasons()` lists the configured seasons with their months.
4. Everything is cached (crops) or copied from config (the rest). No agronomy.

The routes only call these functions; the logic lives here.
"""

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import config

_OBJECTIVES: list[dict[str, str]] = [
    {"key": "gross_margin", "label": "Expected margin", "unit": "USD"},
    {"key": "water_m3", "label": "Water needed", "unit": "m3"},
    {"key": "soil_score", "label": "Soil health", "unit": "0-1"},
]


def _normalise(name: str) -> str:
    return " ".join(name.strip().lower().replace("_", " ").replace("-", " ").split())


@lru_cache(maxsize=1)
def _families() -> dict[str, str]:
    path = Path(config.barc_db).parent / "crop_taxonomy.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {_normalise(name): data.get("family", "") for name, data in raw.items()}


def objectives() -> list[dict[str, str]]:
    """Configured objectives only, in config order."""
    configured = set(config.objectives)
    return [item for item in _OBJECTIVES if item["key"] in configured]


def seasons() -> list[dict[str, Any]]:
    """Season names and months, so the UI does not hardcode them."""
    return [
        {
            "name": season.name,
            "start_month": season.start_month,
            "end_month": season.end_month,
        }
        for season in config.seasons
    ]


@lru_cache(maxsize=1)
def crops() -> list[dict[str, str]]:
    """Distinct crops available in the BARC database, plus the Fallow id."""
    connection = sqlite3.connect(config.barc_db)
    try:
        rows = connection.execute(
            "select distinct crop_id, crop_name from upazila_suitable_crops "
            "order by crop_name"
        ).fetchall()
    finally:
        connection.close()

    families = _families()
    items = [
        {
            "crop_id": str(crop_id),
            "name": str(name),
            "family": families.get(_normalise(str(name)), ""),
        }
        for crop_id, name in rows
    ]
    items.append({"crop_id": "999", "name": "Fallow", "family": "None"})
    return items
