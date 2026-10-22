"""Working fake adapters for S2: payloads come from the stage fixture."""

from __future__ import annotations

from datetime import date
from typing import Any

from ..fixture import load_fixture


class FakeSoilProvider:
    """Serves the soil payload stored in s2_output.json."""

    @property
    def name(self) -> str:
        return "fake_soil"

    async def fetch(
        self,
        *,
        latitude: float = 0.0,
        longitude: float = 0.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return load_fixture()["soil_raw"]


class FakeWeatherProvider:
    """Serves the weather payload stored in s2_output.json."""

    @property
    def name(self) -> str:
        return "fake_weather"

    async def fetch(
        self,
        *,
        latitude: float = 0.0,
        longitude: float = 0.0,
        start_date: date | None = None,
        end_date: date | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return load_fixture()["weather_raw"]
