"""Unit tests for S2 adapters (SoilGrids, Open-Meteo, Fake, HttpClient)."""

from datetime import date
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from cropseq.stages.s2_environment.adapters.fake import FakeSoilProvider, FakeWeatherProvider
from cropseq.stages.s2_environment.adapters.http import HttpClient
from cropseq.stages.s2_environment.adapters.open_meteo import OpenMeteoAdapter
from cropseq.stages.s2_environment.adapters.soilgrids import SoilGridsAdapter


@pytest.mark.anyio
async def test_soilgrids_adapter_query_structure() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.return_value = {"properties": {"layers": []}}

    adapter = SoilGridsAdapter(http_client=mock_http)
    assert adapter.name == "soilgrids"

    res = await adapter.fetch(latitude=36.7378, longitude=-119.7871)
    assert res == {"properties": {"layers": []}}

    mock_http.get_json.assert_called_once()
    call_args = mock_http.get_json.call_args
    assert call_args[0][0] == SoilGridsAdapter.BASE_URL
    params = call_args[1]["params"]

    # Verify query parameters contain lat, lon, properties and depths
    param_dict = dict(params)
    assert ("lat", "36.7378") in params
    assert ("lon", "-119.7871") in params
    assert ("property", "phh2o") in params
    assert ("depth", "0-5cm") in params
    assert ("value", "mean") in params


@pytest.mark.anyio
async def test_open_meteo_adapter_query_structure() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.return_value = {"daily": {"temperature_2m_mean": [20.5]}}

    adapter = OpenMeteoAdapter(http_client=mock_http)
    assert adapter.name == "open_meteo"

    start = date(2025, 1, 1)
    end = date(2025, 1, 10)
    res = await adapter.fetch(
        latitude=36.7378,
        longitude=-119.7871,
        start_date=start,
        end_date=end,
    )
    assert res == {"daily": {"temperature_2m_mean": [20.5]}}

    mock_http.get_json.assert_called_once()
    call_args = mock_http.get_json.call_args
    assert call_args[0][0] == OpenMeteoAdapter.BASE_URL
    params = call_args[1]["params"]
    assert params["latitude"] == 36.7378
    assert params["longitude"] == -119.7871
    assert params["start_date"] == "2025-01-01"
    assert params["end_date"] == "2025-01-10"
    assert "et0_fao_evapotranspiration" in params["daily"]
    assert params["timezone"] == "auto"


@pytest.mark.anyio
async def test_fake_adapters() -> None:
    soil = FakeSoilProvider()
    weather = FakeWeatherProvider()
    assert soil.name == "fake_soil"
    assert weather.name == "fake_weather"

    soil_data = await soil.fetch(latitude=10.0, longitude=20.0)
    assert "properties" in soil_data
    assert "layers" in soil_data["properties"]

    weather_data = await weather.fetch(
        latitude=10.0,
        longitude=20.0,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 2),
    )
    assert "daily" in weather_data


@pytest.mark.anyio
async def test_http_client_retry_and_success() -> None:
    client = HttpClient(timeout=2.0, max_attempts=3)

    call_count = 0
    fake_response = httpx.Response(200, json={"result": "ok"}, request=httpx.Request("GET", "http://test"))
    error_503 = httpx.HTTPStatusError("Service Unavailable", request=httpx.Request("GET", "http://test"), response=httpx.Response(503))

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise error_503
        return fake_response

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        result = await client.get_json("http://test")
        assert result == {"result": "ok"}
        assert call_count == 2
