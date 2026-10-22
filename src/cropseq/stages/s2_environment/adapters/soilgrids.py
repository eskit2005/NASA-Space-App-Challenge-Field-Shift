"""SoilGrids REST API adapter for S2."""

from __future__ import annotations

from typing import Any

from .http import HttpClient


class SoilGridsAdapter:
    """Fetches raw soil properties from ISRIC SoilGrids 2.0 REST API."""

    BASE_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    PROPERTIES = ("phh2o", "clay", "sand", "silt", "soc", "nitrogen")
    DEPTHS = (
        "0-5cm",
        "5-15cm",
        "15-30cm",
        "30-60cm",
        "60-100cm",
        "100-200cm",
    )

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http = http_client or HttpClient()

    @property
    def name(self) -> str:
        return "soilgrids"

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]:
        """Fetch raw SoilGrids JSON payload. Unit scaling is deferred to S3."""
        params: list[tuple[str, str]] = [
            ("lon", str(longitude)),
            ("lat", str(latitude)),
        ]
        for property_name in self.PROPERTIES:
            params.append(("property", property_name))
        for depth in self.DEPTHS:
            params.append(("depth", depth))
        params.append(("value", "mean"))

        return await self.http.get_json(self.BASE_URL, params=params)
