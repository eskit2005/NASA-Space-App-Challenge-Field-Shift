"""Ports (Protocol interfaces) for S2. Adapters implement these."""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol


class SoilDataPort(Protocol):
    """Port for obtaining raw soil data. Normalization belongs to S3."""

    @property
    def name(self) -> str: ...

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any]: ...


class WeatherDataPort(Protocol):
    """Port for obtaining raw historical weather data."""

    @property
    def name(self) -> str: ...

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> dict[str, Any]: ...


class CachePort(Protocol):
    """Port for raw API response cache."""

    def get(self, key: str) -> dict[str, Any] | None: ...

    def set(
        self,
        key: str,
        provider: str,
        request: dict[str, Any],
        response: dict[str, Any],
    ) -> None: ...


# Backward-compatible aliases
SoilProvider = SoilDataPort
WeatherProvider = WeatherDataPort
