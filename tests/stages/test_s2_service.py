"""Unit tests for S2 EnvironmentService orchestration and caching."""

import os
from datetime import date
from unittest.mock import AsyncMock

import pytest

from cropseq.contracts import Location, RawEnvironment
from cropseq.errors import UpstreamUnavailable
from cropseq.stages.s2_environment.cache.sqlite import SQLiteCache
from cropseq.stages.s2_environment.service import EnvironmentService, run


def _weather_provider(name: str, payload: dict) -> AsyncMock:
    provider = AsyncMock()
    provider.name = name
    provider.fetch.return_value = payload
    return provider


@pytest.mark.anyio
async def test_service_cache_hit_and_miss(tmp_path) -> None:
    cache = SQLiteCache(tmp_path / "cache.sqlite")

    mock_soil = AsyncMock()
    mock_soil.name = "soilgrids"
    mock_soil.fetch.return_value = {"phh2o": 65}

    mock_open_meteo = _weather_provider("open_meteo", {"temperature": [22.0]})
    mock_nasa_power = _weather_provider("nasa_power", {"parameters": {"T2M_MAX": 30}})

    service = EnvironmentService(
        soil_provider=mock_soil,
        weather_providers=[mock_open_meteo, mock_nasa_power],
        cache=cache,
    )

    # First call: cache miss, calls all providers.
    res1 = await service.fetch(
        latitude=36.7,
        longitude=-119.7,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )
    assert res1.soil_raw == {"phh2o": 65}
    assert res1.weather_raw == {
        "open_meteo": {"temperature": [22.0]},
        "nasa_power": {"parameters": {"T2M_MAX": 30}},
    }
    assert "(api)" in res1.source
    assert mock_soil.fetch.call_count == 1
    assert mock_open_meteo.fetch.call_count == 1
    assert mock_nasa_power.fetch.call_count == 1

    # Second call with same coordinates: cache hit, no new calls.
    res2 = await service.fetch(
        latitude=36.7,
        longitude=-119.7,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )
    assert res2.soil_raw == {"phh2o": 65}
    assert res2.weather_raw == res1.weather_raw
    assert "(cache)" in res2.source
    assert mock_soil.fetch.call_count == 1
    assert mock_open_meteo.fetch.call_count == 1
    assert mock_nasa_power.fetch.call_count == 1


@pytest.mark.anyio
async def test_service_fails_when_any_weather_source_fails(tmp_path) -> None:
    cache = SQLiteCache(tmp_path / "cache.sqlite")

    mock_soil = AsyncMock()
    mock_soil.name = "soilgrids"
    mock_soil.fetch.return_value = {"phh2o": 65}

    mock_open_meteo = _weather_provider("open_meteo", {"temperature": [22.0]})
    mock_nasa_power = _weather_provider("nasa_power", {})
    mock_nasa_power.fetch.side_effect = RuntimeError("NASA POWER timeout")

    service = EnvironmentService(
        soil_provider=mock_soil,
        weather_providers=[mock_open_meteo, mock_nasa_power],
        cache=cache,
    )

    with pytest.raises(UpstreamUnavailable, match="Sorry, try again"):
        await service.fetch(
            latitude=36.7,
            longitude=-119.7,
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )


@pytest.mark.skipif(
    not os.getenv("CROPSEQ_LIVE"), reason="requires live SoilGrids/Open-Meteo"
)
def test_s2_run_entrypoint() -> None:
    loc = Location(latitude=23.8, longitude=90.4)
    raw = run(loc)
    assert isinstance(raw, RawEnvironment)
    assert raw.soil_raw
    assert raw.weather_raw
    assert raw.fetched_at


def test_get_planning_date_range_standard_and_wrapping(monkeypatch) -> None:
    from cropseq.config import config
    from cropseq.contracts import Season
    from cropseq.stages.s2_environment.service import _get_planning_date_range

    # Standard seasons
    monkeypatch.setattr(
        config,
        "seasons",
        [
            Season(name="s1", start_month=1, end_month=4),
            Season(name="s2", start_month=5, end_month=8),
            Season(name="s3", start_month=9, end_month=12),
        ],
    )
    start, end = _get_planning_date_range(reference_year=2025)
    assert start == date(2025, 1, 1)
    assert end == date(2025, 12, 31)

    # Year-wrapping season (e.g., Nov to Feb)
    monkeypatch.setattr(
        config,
        "seasons",
        [
            Season(name="s1", start_month=11, end_month=2),
            Season(name="s2", start_month=3, end_month=6),
            Season(name="s3", start_month=7, end_month=10),
        ],
    )
    start_wrap, end_wrap = _get_planning_date_range(reference_year=2025)
    assert start_wrap == date(2025, 11, 1)
    assert end_wrap == date(2026, 10, 31)
