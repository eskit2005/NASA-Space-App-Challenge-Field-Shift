"""Open-Meteo adapter for S2.

1. Talks to the Open-Meteo Historical Archive API.
2. Sends latitude, longitude, a date range and three daily variables:
   mean temperature, precipitation and reference evapotranspiration.
3. Returns the raw daily JSON response.
4. Does no aggregation. That belongs to S3.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .http import HttpClient


class OpenMeteoAdapter:
    """Fetches raw daily historical weather data from Open-Meteo."""

    BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
    DAILY_VARIABLES = (
        "temperature_2m_mean",
        "precipitation_sum",
        "et0_fao_evapotranspiration",
    )

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http = http_client or HttpClient()

    @property
    def name(self) -> str:
        return "open_meteo"

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Fetch raw Open-Meteo daily weather JSON payload."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": ",".join(self.DAILY_VARIABLES),
            "timezone": "auto",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }
        return await self.http.get_json(self.BASE_URL, params=params)
