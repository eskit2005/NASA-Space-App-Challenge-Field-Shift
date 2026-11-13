"""Ports for S3 normalization.

1. A port says WHAT data must come back, never HOW it is fetched.
2. `CropCalendarPort` returns raw FAO Crop Calendar records.
3. Country values may be a 2-letter code or a country name.
4. Crop values may be a 4-digit id or a crop name.
5. No normalization happens here; S3 still owns units and aggregation.
"""

from __future__ import annotations

from typing import Any, Protocol


class CropCalendarPort(Protocol):
    """Port for the FAO Crop Calendar API."""

    @property
    def name(self) -> str: ...

    async def fetch_countries(self) -> list[dict[str, Any]]: ...

    async def fetch_crops(self, country: str) -> list[dict[str, Any]]: ...

    async def fetch_aez(self, country: str) -> list[dict[str, Any]]: ...

    async def fetch_calendar(
        self,
        country: str,
        *,
        crops: list[str] | None = None,
        aez: list[str] | None = None,
    ) -> list[dict[str, Any]]: ...
