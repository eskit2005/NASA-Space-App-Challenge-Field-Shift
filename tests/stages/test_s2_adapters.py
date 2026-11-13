"""Unit tests for S2 adapters (SoilGrids, Open-Meteo, HttpClient)."""

from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from cropseq.stages.s2_environment.adapters.http import HttpClient
from cropseq.stages.s2_environment.adapters.open_meteo import OpenMeteoAdapter
from cropseq.stages.s2_environment.adapters.soilgrids import SoilGridsAdapter


@pytest.mark.anyio
async def test_soilgrids_adapter_query_structure() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.return_value = {"properties": {"layers": [{"name": "clay"}]}}

    adapter = SoilGridsAdapter(http_client=mock_http)
    assert adapter.name == "soilgrids"

    res = await adapter.fetch(latitude=36.7378, longitude=-119.7871)

    # Property groups are merged into one payload.
    assert len(res["properties"]["layers"]) == len(adapter.PROPERTY_GROUPS)
    assert res["errors"] == []
    assert mock_http.get_json.call_count == len(adapter.PROPERTY_GROUPS)

    # Each call asks for lat, lon, all depths, mean, and one property group.
    for call, group in zip(
        mock_http.get_json.call_args_list,
        adapter.PROPERTY_GROUPS,
        strict=True,
    ):
        assert call.args[0] == SoilGridsAdapter.BASE_URL
        params = call.kwargs["params"]
        assert ("lat", "36.7378") in params
        assert ("lon", "-119.7871") in params
        assert ("depth", "0-5cm") in params
        assert ("value", "mean") in params
        for name in group:
            assert ("property", name) in params


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
async def test_http_client_retry_and_success() -> None:
    client = HttpClient(timeout=2.0, max_attempts=3)

    call_count = 0
    fake_response = httpx.Response(
        200, json={"result": "ok"}, request=httpx.Request("GET", "http://test")
    )
    error_503 = httpx.HTTPStatusError(
        "Service Unavailable",
        request=httpx.Request("GET", "http://test"),
        response=httpx.Response(503),
    )

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
