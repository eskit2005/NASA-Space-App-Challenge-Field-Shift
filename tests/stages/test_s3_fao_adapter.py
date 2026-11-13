"""Unit tests for the S3 FAO Crop Calendar adapter (no network)."""

from unittest.mock import AsyncMock

import pytest

from cropseq.http import HttpClient
from cropseq.stages.s3_normalization.adapters.fao import FaoCropCalendarAdapter


@pytest.mark.anyio
async def test_countries_query_and_empty_handling() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.return_value = [{"id": "BD", "name": "Bangladesh"}]

    adapter = FaoCropCalendarAdapter(http_client=mock_http)
    assert adapter.name == "fao_crop_calendar"

    countries = await adapter.fetch_countries()
    assert countries == [{"id": "BD", "name": "Bangladesh"}]

    mock_http.get_json.assert_called_once_with(
        FaoCropCalendarAdapter.BASE_URL + "/countries",
        params={"language": "en"},
        empty_statuses={204, 404},
    )

    # 204/404 come back as None from the client and become an empty list.
    mock_http.get_json.reset_mock()
    mock_http.get_json.return_value = None
    assert await adapter.fetch_countries() == []


@pytest.mark.anyio
async def test_calendar_with_country_code_and_ids() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.return_value = [{"crop": {"id": "0024"}}]

    adapter = FaoCropCalendarAdapter(http_client=mock_http)
    records = await adapter.fetch_calendar("BD", crops=["0024"], aez=["003"])

    assert records == [{"crop": {"id": "0024"}}]
    mock_http.get_json.assert_called_once_with(
        FaoCropCalendarAdapter.BASE_URL + "/countries/BD/cropCalendar",
        params={"language": "en", "crop": "0024", "aez": "003"},
        empty_statuses={204, 404},
    )


@pytest.mark.anyio
async def test_calendar_resolves_country_and_crop_names() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.side_effect = [
        [{"id": "BD", "name": "Bangladesh"}],
        [{"crop_id": "0024", "crop_name": "Barley"}],
        [{"crop": {"id": "0024"}}],
    ]

    adapter = FaoCropCalendarAdapter(http_client=mock_http)
    records = await adapter.fetch_calendar("Bangladesh", crops=["Barley"])

    assert records == [{"crop": {"id": "0024"}}]
    assert mock_http.get_json.call_count == 3

    calendar_call = mock_http.get_json.call_args_list[2]
    assert calendar_call.args[0].endswith("/countries/BD/cropCalendar")
    assert calendar_call.kwargs["params"] == {"language": "en", "crop": "0024"}


@pytest.mark.anyio
async def test_crops_and_aez_paths_use_country_code() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.side_effect = [
        [{"crop_id": "0024", "crop_name": "Barley"}],
        [{"zone_id": "003", "name": "Zone 3"}],
    ]

    adapter = FaoCropCalendarAdapter(http_client=mock_http)
    crops = await adapter.fetch_crops("BD")
    zones = await adapter.fetch_aez("BD")

    assert crops[0]["crop_id"] == "0024"
    assert zones[0]["zone_id"] == "003"
    assert mock_http.get_json.call_args_list[0].args[0].endswith("/countries/BD/crops")
    assert mock_http.get_json.call_args_list[1].args[0].endswith("/countries/BD/aez")


@pytest.mark.anyio
async def test_unknown_country_raises() -> None:
    mock_http = AsyncMock(spec=HttpClient)
    mock_http.get_json.return_value = [{"id": "BD", "name": "Bangladesh"}]

    adapter = FaoCropCalendarAdapter(http_client=mock_http)
    with pytest.raises(ValueError, match="FAO country"):
        await adapter.fetch_crops("Narnia")
