"""Unit tests for S2 EnvironmentService orchestration, caching, and fallback."""

from datetime import date
from unittest.mock import AsyncMock

import pytest

from cropseq.contracts import Location, RawEnvironment
from cropseq.stages.s2_environment.cache.sqlite import SQLiteCache
from cropseq.stages.s2_environment.service import EnvironmentService, run


@pytest.mark.anyio
async def test_service_cache_hit_and_miss(tmp_path) -> None:
    cache = SQLiteCache(tmp_path / "cache.sqlite")

    mock_soil = AsyncMock()
    mock_soil.name = "soilgrids"
    mock_soil.fetch.return_value = {"phh2o": 65}

    mock_weather = AsyncMock()
    mock_weather.name = "open_meteo"
    mock_weather.fetch.return_value = {"temperature": [22.0]}

    service = EnvironmentService(
        soil_provider=mock_soil,
        weather_provider=mock_weather,
        cache=cache,
    )

    # First call: cache miss, calls providers
    res1 = await service.fetch(
        latitude=36.7,
        longitude=-119.7,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )
    assert res1.soil_raw == {"phh2o": 65}
    assert res1.weather_raw == {"temperature": [22.0]}
    assert "(api)" in res1.source
    assert mock_soil.fetch.call_count == 1
    assert mock_weather.fetch.call_count == 1

    # Second call with same coordinates: cache hit, no new calls
    res2 = await service.fetch(
        latitude=36.7,
        longitude=-119.7,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )
    assert res2.soil_raw == {"phh2o": 65}
    assert res2.weather_raw == {"temperature": [22.0]}
    assert "(cache)" in res2.source
    assert mock_soil.fetch.call_count == 1
    assert mock_weather.fetch.call_count == 1


@pytest.mark.anyio
async def test_service_fallback_on_api_failure(tmp_path) -> None:
    cache = SQLiteCache(tmp_path / "cache.sqlite")

    failing_soil = AsyncMock()
    failing_soil.name = "soilgrids"
    failing_soil.fetch.side_effect = RuntimeError("ISRIC 503 Outage")

    fallback_soil = AsyncMock()
    fallback_soil.name = "fallback_soil"
    fallback_soil.fetch.return_value = {"phh2o": 70, "fallback": True}

    ok_weather = AsyncMock()
    ok_weather.name = "open_meteo"
    ok_weather.fetch.return_value = {"rain": [5.0]}

    service = EnvironmentService(
        soil_provider=failing_soil,
        weather_provider=ok_weather,
        cache=cache,
        fallback_soil_provider=fallback_soil,
    )

    res = await service.fetch(
        latitude=36.7,
        longitude=-119.7,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )

    assert res.soil_raw == {"phh2o": 70, "fallback": True}
    assert "fallback" in res.source
    assert len(res.warnings) == 1
    assert "ISRIC 503 Outage" in res.warnings[0]


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

