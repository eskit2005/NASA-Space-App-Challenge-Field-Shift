"""S4 fake catalog: read the stage fixture instead of the BARC database.

1. Load `data/data_shape/s4_output.json`.
2. Walk every season's crops and build one BARC-style record per crop.
3. Keep ids stable when the fixture only has text ids (crc32, never `hash()`).
4. Give every fake crop all land types so the fake is usable for unit tests.
5. Return a `CatalogResult` with source `fixture:s4_output`.
"""

from __future__ import annotations

import zlib
from typing import Any

from ..fixture import load_fixture
from ..ports import CatalogResult


def _stable_id(crop_id: str) -> int:
    return 100_000 + zlib.crc32(crop_id.encode()) % 800_000


class FakeCropCatalog:
    """Returns the placeholder crops stored in s4_output.json."""

    def get_records(self, upazila_code: str) -> CatalogResult:
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for season, crops in load_fixture()["by_season"].items():
            for raw in crops:
                crop_id = str(raw["crop_id"])
                if crop_id in seen:
                    continue
                seen.add(crop_id)
                attributes = raw.get("attributes", {})
                records.append(
                    {
                        "crop_id": _stable_id(crop_id),
                        "crop_name": raw["name"],
                        "season": season,
                        "very_suitable_ha": 1000.0,
                        "suitable_ha": 0.0,
                        "mod_suitable_ha": 0.0,
                        "effective_area": float(
                            attributes.get("effective_area_ha", 1000.0)
                        ),
                        "suitability_tier": "Ideal",
                        "family": raw["family"],
                        "root_type": str(attributes.get("root_type", "medium")),
                        "is_legume": bool(
                            attributes.get("is_legume", raw["family"] == "Fabaceae")
                        ),
                        "duration_days": float(
                            attributes.get(
                                "duration_days", attributes.get("growth_days", 100)
                            )
                        ),
                        "yield_t_ha": float(attributes.get("yield_t_ha", 2.0)),
                        "land_types": ["HL", "MHL", "MLL", "LL"],
                    }
                )
        return CatalogResult(
            records=records,
            warnings=[],
            source=f"fixture:s4_output:{upazila_code}",
        )
