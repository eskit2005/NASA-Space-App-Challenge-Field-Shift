"""S2 environment: fetch raw soil + weather data from real APIs.

Order of work:
1. `run(location)` is the public entry point for the stage.
2. `build_environment_service()` picks the adapters from config and opens the cache.
3. `_get_planning_date_range()` turns `config.seasons` into start/end dates.
4. `EnvironmentService.fetch()` checks the cache, calls the adapters for anything
   missing, saves new responses, and returns `RawEnvironment`.
5. The pipeline passes that `RawEnvironment` to S3.

Both weather sources (Open-Meteo and NASA POWER) must succeed for a run to
count. If either fails, S2 raises `UpstreamUnavailable`.

This stage does not clean or convert the data. It only fetches raw payloads.
"""

from __future__ import annotations

import asyncio
import calendar
import concurrent.futures
from collections.abc import Coroutine
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from cropseq.config import config
from cropseq.contracts import FarmerProfile, Location, RawEnvironment
from cropseq.errors import UpstreamUnavailable

from .adapters.nasa_power import NasaPowerAdapter
from .adapters.open_meteo import OpenMeteoAdapter
from .adapters.soilgrids import SoilGridsAdapter
from .cache.sqlite import SQLiteCache, make_cache_key
from .ports import CachePort, SoilDataPort, WeatherDataPort

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S1_OUTPUT = DATA / "s1_output.json"


def _run_coroutine[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from normal sync code.

    Uses a helper thread if an event loop is already running (e.g. inside FastAPI).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


class EnvironmentService:
    """Coordinates the cache and the adapters.

    Steps inside `fetch()`:
    1. Build a cache key for soil and one for each weather provider.
    2. Look all of them up in the cache.
    3. Fetch only the missing ones, at the same time.
    4. Soil failure is a warning; weather failure stops the run.
    5. Save new responses to the cache.
    6. Return both raw payloads inside `RawEnvironment`.
    """

    def __init__(
        self,
        *,
        soil_provider: SoilDataPort,
        weather_providers: list[WeatherDataPort],
        cache: CachePort,
    ) -> None:
        self.soil_provider = soil_provider
        self.weather_providers = weather_providers
        self.cache = cache

    async def fetch(
        self,
        *,
        latitude: float,
        longitude: float,
        start_date: date,
        end_date: date,
    ) -> RawEnvironment:
        """Return raw soil and weather for one location and date range."""
        soil_request = {"latitude": latitude, "longitude": longitude}
        weather_request = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        soil_key = make_cache_key(self.soil_provider.name, soil_request)
        weather_keys = {
            provider.name: make_cache_key(provider.name, weather_request)
            for provider in self.weather_providers
        }

        # 1. Cache lookup: same provider + same request = same key.
        cached_soil = self.cache.get(soil_key)
        cached_weather = {
            provider.name: self.cache.get(weather_keys[provider.name])
            for provider in self.weather_providers
        }

        # 2. Fetch only what the cache does not have. All calls run in parallel.
        tasks: list[Coroutine[Any, Any, dict[str, Any]]] = []
        soil_task_index: int | None = None
        weather_task_indices: dict[str, int] = {}

        if cached_soil is None:
            soil_task_index = len(tasks)
            tasks.append(
                self.soil_provider.fetch(latitude=latitude, longitude=longitude)
            )
        for provider in self.weather_providers:
            if cached_weather[provider.name] is None:
                weather_task_indices[provider.name] = len(tasks)
                tasks.append(
                    provider.fetch(
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

        # 3. Resolve soil: use the cached value, or the fetched one.
        #    A dead soil API must not kill the whole pipeline: continue with
        #    empty soil and report it in `warnings`.
        if cached_soil is not None:
            soil = cached_soil
            soil_source = f"{self.soil_provider.name} (cache)"
        else:
            assert soil_task_index is not None
            soil_res = results[soil_task_index]
            if isinstance(soil_res, Exception):
                soil = {}
                soil_source = "unavailable"
                warnings.append(
                    f"Soil fetch failed, continuing without soil: {soil_res}"
                )
            else:
                soil = soil_res
                soil_source = f"{self.soil_provider.name} (api)"
                self.cache.set(soil_key, self.soil_provider.name, soil_request, soil)

        # A partially failed adapter reports which property groups it lost.
        if isinstance(soil, dict):
            warnings.extend(soil.get("errors", []))

        # 4. Resolve weather: every configured provider must succeed.
        weather: dict[str, dict[str, Any]] = {}
        weather_sources: list[str] = []
        for provider in self.weather_providers:
            name = provider.name
            cached = cached_weather[name]
            if cached is not None:
                weather[name] = cached
                weather_sources.append(f"{name} (cache)")
                continue

            result = results[weather_task_indices[name]]
            if isinstance(result, Exception):
                raise UpstreamUnavailable(
                    f"Sorry, try again. Weather source '{name}' failed: {result}"
                ) from result

            weather[name] = result
            weather_sources.append(f"{name} (api)")
            self.cache.set(weather_keys[name], name, weather_request, result)

        return RawEnvironment(
            soil_raw=soil,
            weather_raw=weather,
            fetched_at=datetime.now(UTC).isoformat(),
            warnings=warnings,
            source=f"soil:{soil_source}, weather:{', '.join(weather_sources)}",
        )


def _build_soil_provider(name: str) -> SoilDataPort:
    """Return the soil adapter for a config name. Only 'soilgrids' exists."""
    if name == "soilgrids":
        return SoilGridsAdapter()
    raise NotImplementedError(
        f"Soil adapter '{name}' is not supported. Supported: 'soilgrids'."
    )


def _build_weather_providers(names: list[str]) -> list[WeatherDataPort]:
    """Return one weather adapter per config name.

    Supported: 'openmeteo'/'open_meteo' and 'nasa_power'.
    """
    providers: list[WeatherDataPort] = []
    for name in names:
        key = name.strip().lower()
        if key in {"openmeteo", "open_meteo"}:
            providers.append(OpenMeteoAdapter())
        elif key in {"nasa_power", "nasa"}:
            providers.append(NasaPowerAdapter())
        else:
            raise NotImplementedError(
                f"Weather adapter '{name}' is not supported. "
                "Supported: 'openmeteo', 'nasa_power'."
            )
    if not providers:
        raise NotImplementedError("At least one weather adapter is required.")
    return providers


def _get_planning_date_range(reference_year: int = 2025) -> tuple[date, date]:
    """Turn `config.seasons` into one continuous date range.

    Example: seasons Jan-Apr, May-Aug, Sep-Dec -> 2025-01-01 .. 2025-12-31.
    A season that wraps the year (Nov-Feb) pushes the end date to the next year.
    """
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
    """Build the service from config.

    1. Read the soil adapter name (default 'soilgrids').
    2. Read the weather adapter names (default 'openmeteo,nasa_power').
    3. Create all adapters and the SQLite cache.
    """
    soil_adapter_name = soil_name or config.adapters.get("soil", "soilgrids")
    weather_spec = weather_name or config.adapters.get(
        "weather", "openmeteo,nasa_power"
    )
    weather_names = [name for name in weather_spec.split(",") if name.strip()]
    db_path = cache_path or config.cache_db

    soil_provider = _build_soil_provider(soil_adapter_name)
    weather_providers = _build_weather_providers(weather_names)
    cache = SQLiteCache(db_path)

    return EnvironmentService(
        soil_provider=soil_provider,
        weather_providers=weather_providers,
        cache=cache,
    )


def run(location: Location | None = None) -> RawEnvironment:
    """Fetch raw soil + weather payloads for the farm location.

    Steps:
    1. Use the given location. If none, load it from s1_output.json.
    2. Build the service (adapters + cache).
    3. Compute the date range from config.seasons.
    4. Run the async fetch and return RawEnvironment.

    Standalone: loads the location from s1_output.json.
    """
    if location is None:
        location = FarmerProfile.model_validate_json(
            S1_OUTPUT.read_text(encoding="utf-8")
        ).location
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
