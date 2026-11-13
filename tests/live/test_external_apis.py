"""Live checks for the external APIs used by cropseq. Prints the payload shape.

1. Import the adapters for the S2 APIs (SoilGrids, Open-Meteo).
2. Hit SoilGrids and print its layers and depth values.
3. Hit Open-Meteo and print its daily series sizes.
4. Hit NASA POWER and print its parameter definitions and data coverage.
5. Hit the FAO Crop Calendar API:
   a. countries lookup (A),
   b. crops lookup (B),
   c. agro-ecological zones lookup (C),
   d. full calendar data (D), with and without filters,
   e. Excel export (E).
6. Resolve country/crop names to raw IDs before calling endpoint D.
7. Retry 429/5xx responses with exponential backoff.
8. Treat 404 and 204 as "no data" (return an empty list).
9. Normalize the calendar payload into a flat planting/harvest/sowing summary.
"""

import asyncio
import unicodedata
from datetime import date

import httpx
import pytest

from cropseq.stages.s2_environment.adapters.open_meteo import OpenMeteoAdapter
from cropseq.stages.s2_environment.adapters.soilgrids import SoilGridsAdapter

LATITUDE = 24.0
LONGITUDE = 90.0

# FAO Crop Calendar API. The task sheet says "https://fao.org"; the live API is here.
FAO_BASE_URL = "https://api-cropcalendar.apps.fao.org/api/v1"
FAO_LANGUAGE = "en"
FAO_COUNTRY_NAME = "Cabo Verde"
FAO_COUNTRY_CODE = "CV"
FAO_CROP_NAME = "Corn, sweet"
FAO_CROP_ID = "0113"

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
POWER_PARAMETERS = [
    "GDD10",
    "PRECTOTCORR",
    "GWETTOP",
    "GWETROOT",
    "GWETPROF",
    "TS",
    "ALLSKY_SFC_SW_DWN",
    "EVPTRNS",
    "EVLAND",
    "RH2M",
    "WS10M",
    "SNODP",
    "T2M_MAX",
    "T2M_MIN",
    "T2MWET",
    "PS",
    "ALLSKY_SFC_SW_DNI",
    "ALLSKY_SFC_SW_DIFF",
]


@pytest.mark.anyio
async def test_soilgrids_raw() -> None:
    payload = await SoilGridsAdapter().fetch(
        latitude=LATITUDE,
        longitude=LONGITUDE,
    )

    print("\nSoilGrids top-level:", sorted(payload))
    layers = payload.get("properties", {}).get("layers", [])
    print("SoilGrids layers:", len(layers))
    print("SoilGrids errors:", payload.get("errors", []))
    for layer in layers:
        measure = layer.get("unit_measure", {})
        print(
            f"  {layer.get('name')}: mapped={measure.get('mapped_units')} "
            f"target={measure.get('target_units')} "
            f"d_factor={measure.get('d_factor')}"
        )
        for depth in layer.get("depths", []):
            values = depth.get("values", {})
            print(f"    {depth.get('label')}: mean={values.get('mean')}")

    names = {layer.get("name") for layer in layers}
    assert names == set(SoilGridsAdapter.PROPERTIES)


@pytest.mark.anyio
async def test_open_meteo_raw() -> None:
    payload = await OpenMeteoAdapter().fetch(
        latitude=LATITUDE,
        longitude=LONGITUDE,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )

    print("\nOpen-Meteo top-level:", sorted(payload))
    daily = payload.get("daily", {})
    print("Open-Meteo daily:")
    for name, values in daily.items():
        size = len(values) if isinstance(values, list) else "scalar"
        print(f"  {name}: {size}")

    assert daily


@pytest.mark.anyio
async def test_nasa_power_raw() -> None:
    query = {
        "parameters": ",".join(POWER_PARAMETERS),
        "community": "AG",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start": "20250101",
        "end": "20251231",
        "format": "JSON",
        "header": "true",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.get(POWER_URL, params=query)

    print("\nNASA POWER status:", response.status_code)
    if response.status_code != 200:
        print("NASA POWER body:", response.text[:3000])
    assert response.status_code == 200

    payload = response.json()
    print("NASA POWER top-level:", sorted(payload))

    header = payload.get("header", {})
    print("NASA POWER header:", header)

    definitions = payload.get("parameters", {})
    print("NASA POWER parameter definitions:")
    for name, meta in definitions.items():
        print(f"  {name}: units={meta.get('units')} longname={meta.get('longname')}")

    data = payload.get("properties", {}).get("parameter", {})
    print("NASA POWER returned parameters:", sorted(data))
    for name, series in data.items():
        dates = sorted(series)
        if not dates:
            print(f"  {name}: empty")
            continue
        fill_count = sum(1 for value in series.values() if value == -999)
        print(
            f"  {name}: {len(dates)} days, "
            f"first {dates[0]}={series[dates[0]]}, "
            f"last {dates[-1]}={series[dates[-1]]}, "
            f"fill(-999)={fill_count}"
        )

    assert data


# ---------------------------------------------------------------------------
# FAO Crop Calendar API
# ---------------------------------------------------------------------------


def _slug(value: str) -> str:
    """Lowercase and strip accents so "Cabo Verde" matches "Cabo Verde"."""
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip().lower()


async def _fao_request(
    path: str, params: dict | None = None, attempts: int = 3
) -> httpx.Response:
    """GET an FAO path, retrying 429/5xx with exponential backoff."""
    query = {"language": FAO_LANGUAGE}
    if params:
        query.update(params)

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, attempts + 1):
            response = await client.get(FAO_BASE_URL + path, params=query)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == attempts:
                    response.raise_for_status()
                await asyncio.sleep(0.5 * 2 ** (attempt - 1))
                continue
            return response
    raise AssertionError("retry loop ended without a response")


async def _fao_json(path: str, params: dict | None = None) -> list[dict]:
    """Return JSON data; 404 and 204 mean "no data", so return []."""
    response = await _fao_request(path, params)
    if response.status_code in (204, 404):
        return []
    response.raise_for_status()
    return response.json()


def _resolve_country(countries: list[dict], value: str) -> dict:
    """Resolve a country id ("CV") or name ("Cabo Verde") to a country record."""
    target = _slug(value)
    for country in countries:
        if country["id"].upper() == value.strip().upper():
            return country
    for country in countries:
        if _slug(country["name"]) == target:
            return country
    names = ", ".join(f"{c['id']}={c['name']}" for c in countries[:10])
    raise AssertionError(f"Country {value!r} not found. Sample: {names}")


def _resolve_crop(crops: list[dict], value: str) -> dict:
    """Resolve a crop id ("0113") or name ("Corn, sweet") to a crop record."""
    target = _slug(value)
    for crop in crops:
        if crop["crop_id"] == value.strip():
            return crop
    for crop in crops:
        if _slug(crop.get("crop_name", "")) == target:
            return crop
    for crop in crops:
        if _slug(crop.get("crop_name", "")).startswith(target):
            return crop
    names = ", ".join(f"{c['crop_id']}={c['crop_name']}" for c in crops[:10])
    raise AssertionError(f"Crop {value!r} not found. Sample: {names}")


def _normalize_calendar(records: list[dict], country: str | None = None) -> list[dict]:
    """Flatten API records into one row per crop/AEZ/session."""
    summary = []
    for record in records:
        crop = record.get("crop", {})
        aez = record.get("aez", {})
        for session in record.get("sessions", []):
            summary.append(
                {
                    "country": record.get("id_country") or country,
                    "crop_id": crop.get("id"),
                    "crop_name": crop.get("name"),
                    "aez_id": aez.get("id"),
                    "aez_name": aez.get("name"),
                    "planting_early": session.get("early_sowing"),
                    "planting_late": session.get("later_sowing"),
                    "harvest_early": session.get("early_harvest"),
                    "harvest_late": session.get("late_harvest"),
                    "growing_period": session.get("growing_period"),
                    "sowing_rate": session.get("sowing_rate"),
                    "all_year": session.get("all_year"),
                    "water_notes": session.get("additional_information"),
                    "comments": session.get("comments"),
                }
            )
    return summary


@pytest.mark.anyio
async def test_fao_countries_lookup() -> None:
    countries = await _fao_json("/countries")

    print("\nFAO countries:", len(countries))
    print("FAO sample:", countries[:3])

    assert countries
    assert all({"id", "name"} <= set(country) for country in countries)
    country = _resolve_country(countries, FAO_COUNTRY_NAME)
    assert country["id"] == FAO_COUNTRY_CODE


@pytest.mark.anyio
async def test_fao_crops_lookup() -> None:
    countries = await _fao_json("/countries")
    country = _resolve_country(countries, FAO_COUNTRY_NAME)
    crops = await _fao_json(f"/countries/{country['id']}/crops")

    print("\nFAO crops:", len(crops))
    print("FAO crop keys:", sorted(crops[0]))

    assert crops
    assert {"crop_id", "crop_name", "crop_scientific_name"} <= set(crops[0])
    crop = _resolve_crop(crops, FAO_CROP_NAME)
    assert crop["crop_id"] == FAO_CROP_ID
    crop_by_id = _resolve_crop(crops, FAO_CROP_ID)
    assert crop_by_id["crop_id"] == FAO_CROP_ID


@pytest.mark.anyio
async def test_fao_aez_lookup() -> None:
    crops = await _fao_json(f"/countries/{FAO_COUNTRY_CODE}/crops")
    zones = await _fao_json(f"/countries/{FAO_COUNTRY_CODE}/aez")

    print("\nFAO zones:", len(zones))
    print("FAO zone keys:", sorted(zones[0]))

    assert zones
    assert {"zone_id", "name"} <= set(zones[0])
    assert crops


@pytest.mark.anyio
async def test_fao_crop_calendar_all() -> None:
    records = await _fao_json(f"/countries/{FAO_COUNTRY_CODE}/cropCalendar")

    print("\nFAO calendar records:", len(records))
    print("FAO record keys:", sorted(records[0]))
    print("FAO session keys:", sorted(records[0]["sessions"][0]))
    print("FAO first record:", records[0])

    assert records
    assert {"crop", "aez", "sessions", "lastUpdated"} <= set(records[0])
    assert any(record["sessions"] for record in records)


@pytest.mark.anyio
async def test_fao_crop_calendar_filtered_by_names() -> None:
    countries = await _fao_json("/countries")
    country = _resolve_country(countries, FAO_COUNTRY_NAME)
    crops = await _fao_json(f"/countries/{country['id']}/crops")
    crop = _resolve_crop(crops, FAO_CROP_NAME)

    records = await _fao_json(
        f"/countries/{country['id']}/cropCalendar", {"crop": crop["crop_id"]}
    )
    summary = _normalize_calendar(records, country["id"])

    print("\nFAO filtered records:", len(records))
    print("FAO filtered summary rows:", len(summary))
    print("FAO summary sample:", summary[0] if summary else None)

    assert records
    assert all(record["crop"]["id"] == crop["crop_id"] for record in records)
    assert summary
    assert all(row["crop_id"] == crop["crop_id"] for row in summary)
    assert any(row["planting_early"] for row in summary)
    assert any(row["harvest_early"] for row in summary)
    assert any(row["growing_period"] for row in summary)


@pytest.mark.anyio
async def test_fao_crop_calendar_missing_data() -> None:
    no_crop = await _fao_json(
        f"/countries/{FAO_COUNTRY_CODE}/cropCalendar", {"crop": "9999"}
    )
    no_country = await _fao_json("/countries/ZZ/cropCalendar")

    print("\nFAO unknown crop:", no_crop)
    print("FAO unknown country:", no_country)

    assert no_crop == []
    assert no_country == []


@pytest.mark.anyio
async def test_fao_calendar_excel_download(tmp_path) -> None:
    response = await _fao_request(
        f"/countries/{FAO_COUNTRY_CODE}/cropCalendar/download",
        {"crop": FAO_CROP_ID},
    )

    print("\nFAO Excel status:", response.status_code)
    print("FAO Excel type:", response.headers.get("content-type"))

    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    target = tmp_path / "crop_calendar.xlsx"
    target.write_bytes(response.content)
    assert target.stat().st_size > 0
