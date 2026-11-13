"""Ports (Protocol interfaces) for S4 crop data.

1. `CatalogResult` is the small envelope a catalog returns: records, warnings
   and a short source label.
2. `CropCatalog` is the port. `barc.py` reads the local BARC SQLite database
   (and fetches from BARC CZIS on a cache miss); `fake.py` reads the fixture.
3. Records are plain dictionaries because BARC rows have many optional columns;
   `selection.py` turns the survivors into the shared `Crop` contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class CatalogResult:
    """What a crop catalog returns for one upazila."""

    records: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source: str = ""


class CropCatalog(Protocol):
    """Supplies BARC-style crop suitability records for one upazila."""

    def get_records(self, upazila_code: str) -> CatalogResult: ...
