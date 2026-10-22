"""S2 environment: fetch raw soil + weather payloads via Ports & Adapters."""

from __future__ import annotations

import asyncio
import calendar
import concurrent.futures
from datetime import date, datetime, timezone
from typing import Any, Coroutine, TypeVar

from cropseq.config import config
from cropseq.contracts import Location, RawEnvironment

from .adapters.fake import FakeSoilProvider, FakeWeatherProvider
from .adapters.open_meteo import OpenMeteoAdapter
from .adapters.soilgrids import SoilGridsAdapter
from .cache.sqlite import SQLiteCache, make_cache_key
from .ports import CachePort, SoilDataPort, WeatherDataPort

T = TypeVar("T")


def _run_coroutine(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine synchronously, handling already-running event loops."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class EnvironmentService:
    """Coordinates fetching and caching raw environmental data across external providers."""

    def __init__(
        self,
        *,
        soil_provider: SoilDataPort,
        weather_provider: WeatherDataPort,
        cache: CachePort,
        fallback_soil_provider: SoilDataPort | None = None,
        fallback_weather_provider: WeatherDataPort | None = None,
    ) -> None:
        self.soil_provider = soil_provider
        self.weather_provider = weather_provider
        self.cache = cache
        self.fallback_soil_provider = fallback_soil_provider
        self.fallback_weather_provider = fallback_weather_provider

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> RawEnvironment:
        soil_request = {"latitude": latitude, "longitude": longitude}
        weather_request = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        soil_key = make_cache_key(self.soil_provider.name, soil_request)
        weather_key = make_cache_key(self.weather_provider.name, weather_request)

        # 1. Cache lookup
        cached_soil = self.cache.get(soil_key)
        cached_weather = self.cache.get(weather_key)

        # 2. Fetch missing in parallel
        tasks = []
        task_indices: dict[str, int] = {}
        if cached_soil is None:
            task_indices["soil"] = len(tasks)
            tasks.append(self.soil_provider.fetch(latitude=latitude, longitude=longitude))
        if cached_weather is None:
            task_indices["weather"] = len(tasks)
            tasks.append(
                self.weather_provider.fetch(
                    latitude=latitude,
                    longitude=longitude,
                    start_date=start_date,
                    end_date=end_date,
                )
            )

        results: list[Any] = (
            await asyncio.gather(*tasks, return_exceptions=True) if tasks else []
        )

        warnings: list[str] = []

        # 3. Resolve soil
        if cached_soil is not None:
            soil = cached_soil
            soil_source = f"{self.soil_provider.name} (cache)"
        else:
            soil_res = results[task_indices["soil"]]
            if isinstance(soil_res, Exception):
                if self.fallback_soil_provider is not None:
                    soil = await self.fallback_soil_provider.fetch(
                        latitude=latitude, longitude=longitude
                    )
                    soil_source = f"{self.fallback_soil_provider.name} (fallback)"
                    warnings.append(
                        f"Soil provider '{self.soil_provider.name}' failed: {soil_res}. Used fallback."
                    )
                else:
                    raise soil_res
            else:
                soil = soil_res
                soil_source = f"{self.soil_provider.name} (api)"
                self.cache.set(soil_key, self.soil_provider.name, soil_request, soil)

        # 4. Resolve weather
        if cached_weather is not None:
            weather = cached_weather
            weather_source = f"{self.weather_provider.name} (cache)"
        else:
            weather_res = results[task_indices["weather"]]
            if isinstance(weather_res, Exception):
                if self.fallback_weather_provider is not None:
                    weather = await self.fallback_weather_provider.fetch(
                        latitude=latitude,
                        longitude=longitude,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    weather_source = f"{self.fallback_weather_provider.name} (fallback)"
                    warnings.append(
                        f"Weather provider '{self.weather_provider.name}' failed: {weather_res}. Used fallback."
                    )
                else:
                    raise weather_res
            else:
                weather = weather_res
                weather_source = f"{self.weather_provider.name} (api)"
                self.cache.set(weather_key, self.weather_provider.name, weather_request, weather)

        return RawEnvironment(
            soil_raw=soil,
            weather_raw=weather,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            warnings=warnings,
            source=f"soil:{soil_source}, weather:{weather_source}",
        )


def _build_soil_provider(name: str) -> SoilDataPort:
    if name == "fake":
        return FakeSoilProvider()
    if name == "soilgrids":
        return SoilGridsAdapter()
    raise NotImplementedError(
        f"Soil adapter '{name}' is not supported. Supported: 'fake', 'soilgrids'."
    )


def _build_weather_provider(name: str) -> WeatherDataPort:
    if name == "fake":
        return FakeWeatherProvider()
    if name in {"openmeteo", "open_meteo"}:
        return OpenMeteoAdapter()
    raise NotImplementedError(
        f"Weather adapter '{name}' is not supported. Supported: 'fake', 'openmeteo'."
    )


def _get_planning_date_range(reference_year: int = 2025) -> tuple[date, date]:
    """Derive chronological date range across configured seasons, handling year-wrapping."""
    if not config.seasons:
        return date(reference_year, 1, 1), date(reference_year, 12, 31)

    start_year = reference_year
    start_month = config.seasons[0].start_month
    start_date = date(start_year, start_month, 1)

    current_year = start_year
    prev_end_month = start_month

    for i, season in enumerate(config.seasons):
        if i > 0 and season.start_month <= prev_end_month:
            current_year += 1
        if season.end_month < season.start_month:
            current_year += 1
        prev_end_month = season.end_month

    _, last_day = calendar.monthrange(current_year, config.seasons[-1].end_month)
    return start_date, date(current_year, config.seasons[-1].end_month, last_day)


def build_environment_service(
    *,
    soil_name: str | None = None,
    weather_name: str | None = None,
    cache_path: str | None = None,
) -> EnvironmentService:
    """Factory creating an EnvironmentService using current config and fallback defaults."""
    soil_adapter_name = soil_name or config.adapters.get("soil", "fake")
    weather_adapter_name = weather_name or config.adapters.get("weather", "fake")
    db_path = cache_path or config.cache_db

    soil_provider = _build_soil_provider(soil_adapter_name)
    weather_provider = _build_weather_provider(weather_adapter_name)
    cache = SQLiteCache(db_path)

    return EnvironmentService(
        soil_provider=soil_provider,
        weather_provider=weather_provider,
        cache=cache,
        fallback_soil_provider=FakeSoilProvider(),
        fallback_weather_provider=FakeWeatherProvider(),
    )


def run(location: Location) -> RawEnvironment:
    """Fetch raw soil + weather payloads for the farm location."""
    service = build_environment_service()
    start_date, end_date = _get_planning_date_range()

    return _run_coroutine(
        service.fetch(
            latitude=location.latitude,
            longitude=location.longitude,
            start_date=start_date,
            end_date=end_date,
        )
    )
