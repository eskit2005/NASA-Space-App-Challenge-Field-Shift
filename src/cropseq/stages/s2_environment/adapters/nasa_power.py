"""NASA POWER adapter for S2.

1. Talks to the NASA POWER daily point API (community "AG").
2. Sends latitude, longitude, a date range and a fixed list of agro-climate
   parameters (heat, water, evaporation, radiation).
3. Returns the raw JSON response.
4. Does no cleaning: -999 fill values, units and missing days belong to S3.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .http import HttpClient


class NasaPowerAdapter:
    """Fetches raw daily agro-climate data from NASA POWER."""

    BASE_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
    TIMEOUT_S = 120.0
    PARAMETERS = (
        "GDD10",
        "PRECTOTCORR",
        "GWETTOP",
        "GWETROOT",
        "GWETPROF",
        "TS",
        "ALLSKY_SFC_SW_DWN",
        "EVPTRNS",
        "EVLAND",
        "RH2M",
        "WS10M",
        "SNODP",
        "T2M_MAX",
        "T2M_MIN",
        "T2MWET",
        "PS",
        "ALLSKY_SFC_SW_DNI",
        "ALLSKY_SFC_SW_DIFF",
    )

    def __init__(self, http_client: HttpClient | None = None) -> None:
        self.http = http_client or HttpClient(timeout=self.TIMEOUT_S, max_attempts=2)

    @property
    def name(self) -> str:
        return "nasa_power"

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]:
        """Fetch raw NASA POWER daily JSON payload."""
        params = {
            "parameters": ",".join(self.PARAMETERS),
            "community": "AG",
            "latitude": latitude,
            "longitude": longitude,
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "format": "JSON",
            "header": "true",
        }
        return await self.http.get_json(self.BASE_URL, params=params)
