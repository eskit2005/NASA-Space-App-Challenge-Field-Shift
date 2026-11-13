"""FAO Crop Calendar adapter for S3.

1. Talks to `https://api-cropcalendar.apps.fao.org/api/v1`.
2. Every request sends `language=en` (FAO ignores `lang`).
3. `fetch_countries()` returns the country list (name -> code lookup).
4. `fetch_crops()` and `fetch_aez()` accept a 2-letter code or a country name.
5. `fetch_calendar()` accepts crop names or 4-digit ids, plus optional AEZ ids.
6. 204 and 404 mean "no data" and return an empty list.
7. Returns raw records only. Normalization belongs to S3's service.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from cropseq.http import HttpClient


def _slug(value: str) -> str:
    """Lowercase and strip accents so names compare reliably."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip().lower()


class FaoCropCalendarAdapter:
    """Fetches raw crop-calendar records from the FAO API."""

    BASE_URL = "https://api-cropcalendar.apps.fao.org/api/v1"
    TIMEOUT_S = 30.0

    def __init__(
        self,
        http_client: HttpClient | None = None,
        *,
        language: str = "en",
    ) -> None:
        self.http = http_client or HttpClient(timeout=self.TIMEOUT_S, max_attempts=3)
        self.language = language

    @property
    def name(self) -> str:
        return "fao_crop_calendar"

    async def _get(self, path: str, params: dict[str, str] | None = None) -> list[Any]:
        """GET an FAO path; 204/404 become an empty list."""
        query = {"language": self.language}
        if params:
            query.update(params)
        result = await self.http.get_json(
            self.BASE_URL + path,
            params=query,
            empty_statuses={204, 404},
        )
        return result if isinstance(result, list) else []

    async def fetch_countries(self) -> list[dict[str, Any]]:
        """Return every country FAO has data for."""
        return await self._get("/countries")

    async def _country_code(self, country: str) -> str:
        """Resolve a 2-letter code or a country name to a 2-letter code."""
        value = country.strip()
        if len(value) == 2 and value.isalpha():
            return value.upper()

        target = _slug(value)
        countries = await self.fetch_countries()
        for record in countries:
            if _slug(record.get("name", "")) == target:
                return record["id"].upper()
        for record in countries:
            if _slug(record.get("name", "")).startswith(target):
                return record["id"].upper()
        raise ValueError(f"FAO country {country!r} not found")

    async def fetch_crops(self, country: str) -> list[dict[str, Any]]:
        """Return the crops that have a calendar in `country`."""
        code = await self._country_code(country)
        return await self._get(f"/countries/{code}/crops")

    async def fetch_aez(self, country: str) -> list[dict[str, Any]]:
        """Return the agro-ecological zones of `country`."""
        code = await self._country_code(country)
        return await self._get(f"/countries/{code}/aez")

    @staticmethod
    def _resolve_crop(crops: list[dict[str, Any]], value: str) -> str:
        """Resolve a 4-digit crop id or a crop name to a crop id."""
        target = _slug(value)
        for record in crops:
            if record.get("crop_id") == value.strip():
                return record["crop_id"]
        for record in crops:
            if _slug(record.get("crop_name", "")) == target:
                return record["crop_id"]
        for record in crops:
            if _slug(record.get("crop_name", "")).startswith(target):
                return record["crop_id"]
        raise ValueError(f"FAO crop {value!r} not found in this country")

    async def fetch_calendar(
        self,
        country: str,
        *,
        crops: list[str] | None = None,
        aez: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return raw calendar records for a country, optionally filtered."""
        code = await self._country_code(country)
        params: dict[str, str] = {}

        if crops:
            catalog: list[dict[str, Any]] | None = None
            crop_ids: list[str] = []
            for crop in crops:
                value = crop.strip()
                if value.isdigit():
                    crop_ids.append(value)
                    continue
                if catalog is None:
                    catalog = await self.fetch_crops(code)
                crop_ids.append(self._resolve_crop(catalog, value))
            params["crop"] = ",".join(crop_ids)

        if aez:
            params["aez"] = ",".join(zone.strip() for zone in aez if zone.strip())

        return await self._get(f"/countries/{code}/cropCalendar", params or None)
