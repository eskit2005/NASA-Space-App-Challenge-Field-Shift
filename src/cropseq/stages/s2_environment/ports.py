"""Ports for S2: the interfaces this stage depends on.

1. A port says WHAT data must come back, never HOW it is fetched.
2. `SoilDataPort` returns the raw soil payload.
3. `WeatherDataPort` returns the raw weather payload.
4. `CachePort` stores and reads raw payloads by key.

Adapters in `adapters/` implement these. `service.py` imports only the ports.
"""

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
