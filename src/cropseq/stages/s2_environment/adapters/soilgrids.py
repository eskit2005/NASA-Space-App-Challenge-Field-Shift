"""SoilGrids adapter for S2.

1. Talks to the ISRIC SoilGrids 2.0 REST API.
2. Sends latitude, longitude, nine soil properties and six depths.
3. Splits the properties into three groups and runs them at the same time,
   so one slow group cannot block the others.
4. Returns one merged raw JSON payload. A failed group is listed in `errors`.
5. Uses a long timeout (180s) because ISRIC can take minutes on a cold call.
6. Does no unit conversion. That belongs to S3.
7. `d_factor` in the response tells S3 how to convert each value.
"""

from __future__ import annotations

import asyncio
from typing import Any

from .http import HttpClient


class SoilGridsAdapter:
    """Fetches raw soil properties from ISRIC SoilGrids 2.0 REST API."""

    BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    TIMEOUT_S = 180.0

    PROPERTY_GROUPS = (
        ("clay", "sand", "silt"),
        ("bdod", "cfvo", "phh2o"),
        ("soc", "nitrogen", "cec"),
    )
    PROPERTIES = tuple(name for group in PROPERTY_GROUPS for name in group)
    DEPTHS = (
        "0-5cm",
        "5-15cm",
        "15-30cm",
        "30-60cm",
        "60-100cm",
        "100-200cm",
    )

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http = http_client or HttpClient(timeout=self.TIMEOUT_S, max_attempts=2)

    @property
    def name(self) -> str:
        return "soilgrids"

    def _params(
        self,
        *,
        latitude: float,
        longitude: float,
        properties: tuple[str, ...],
    ) -> list[tuple[str, str]]:
        """Build the query for one property group."""
        params: list[tuple[str, str]] = [
            ("lon", str(longitude)),
            ("lat", str(latitude)),
        ]
        for property_name in properties:
            params.append(("property", property_name))
        for depth in self.DEPTHS:
            params.append(("depth", depth))
        params.append(("value", "mean"))
        return params

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        """Fetch all property groups and merge them into one raw payload."""
        requests = [
            self.http.get_json(
                self.BASE_URL,
                params=self._params(
                    latitude=latitude,
                    longitude=longitude,
                    properties=group,
                ),
            )
            for group in self.PROPERTY_GROUPS
        ]
        results = await asyncio.gather(*requests, return_exceptions=True)

        layers: list[dict[str, Any]] = []
        errors: list[str] = []
        geometry: dict[str, Any] | None = None

        for group, result in zip(self.PROPERTY_GROUPS, results, strict=True):
            if isinstance(result, Exception):
                errors.append(f"{','.join(group)}: {result}")
                continue
            geometry = geometry or result.get("geometry")
            layers.extend(result.get("properties", {}).get("layers", []))

        if not layers and errors:
            raise RuntimeError(
                "SoilGrids failed for all property groups: " + "; ".join(errors)
            )

        return {
            "type": "Feature",
            "geometry": geometry,
            "properties": {"layers": layers},
            "errors": errors,
        }
