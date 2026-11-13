"""S4 tests: routing, taxonomy, land-type filtering, bucketing and BARC caching.

1. Routing tests use the committed upazila polygons and known benchmark points.
2. Taxonomy tests check every crop name in the committed BARC database.
3. Selection tests use the committed BARC database (read-only, no network).
4. Catalog tests copy the database to a temp file and inject a fake HTTP client.
5. Service tests cover the Bangladesh path and the "not supported yet" path.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest

from cropseq.config import config
from cropseq.contracts import Environment, LandTypeCheck, Location, SoilProfile
from cropseq.stages.s4_filtering.adapters.barc import BarcCatalog
from cropseq.stages.s4_filtering.router import UpazilaRouter
from cropseq.stages.s4_filtering.selection import (
    canonical_land_type,
    select_candidate_pools,
)
from cropseq.stages.s4_filtering.service import run
from cropseq.stages.s4_filtering.taxonomy import (
    is_perennial,
    resolve_taxonomy,
)

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "bangladesh" / "crop_recommender.db"
POLYGONS = ROOT / "data" / "bangladesh" / "upazila_polygons.json"
SEASONS = [season.name for season in config.seasons]

RANINAGAR = (24.78, 89.04)
DOWARABAZAR = (25.05, 91.56)
CHARGHAT = (24.28, 88.75)
MONGLA = (22.1532, 89.6591)
GODAGARI = (24.47, 88.33)
BELKUCHI = (24.30, 89.75)
NAIROBI = (-1.29, 36.82)


def _pools(lat: float, lon: float, land_type: str):
    route = UpazilaRouter(POLYGONS).route(lat, lon)
    result = BarcCatalog(DB).get_records(route.upazila_code)
    return route, select_candidate_pools(
        result.records, land_type, route.district_name, SEASONS
    )


def _names(pools, season: str) -> set[str]:
    return {crop.name.lower() for crop in pools.by_season[season]}


def test_router_benchmark_points() -> None:
    router = UpazilaRouter(POLYGONS)

    raninagar = router.route(*RANINAGAR)
    assert raninagar.upazila_name == "Raninagar"
    assert raninagar.district_name == "Naogaon"
    assert raninagar.is_bangladesh is True

    dowarabazar = router.route(*DOWARABAZAR)
    assert dowarabazar.upazila_name == "Dowarabazar"
    assert dowarabazar.district_name == "Sunamganj"

    charghat = router.route(*CHARGHAT)
    assert charghat.upazila_name == "Charghat"

    mongla = router.route(*MONGLA)
    assert mongla.upazila_name == "Mongla"

    outside = router.route(*NAIROBI)
    assert outside.is_bangladesh is False
    assert outside.method == "national_envelope_rejection"


def test_taxonomy_covers_every_cached_crop() -> None:
    connection = sqlite3.connect(DB)
    try:
        names = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT crop_name FROM upazila_suitable_crops"
            )
        ]
    finally:
        connection.close()

    for name in names:
        entry = resolve_taxonomy(name)
        assert entry is not None, name
        assert entry["family"] != "Unknown", name

    ground_nut = resolve_taxonomy("Ground Nut")
    assert ground_nut["family"] == "Fabaceae"
    assert ground_nut["is_legume"] is True

    assert is_perennial("Mango") is True
    assert is_perennial("Tea") is True
    assert is_perennial("Teasle Gourd") is False
    assert is_perennial("Boro dhan") is False


def test_raninagar_mhl_rabi_keeps_potato_and_sunflower() -> None:
    route, pools = _pools(*RANINAGAR, "MHL")
    assert route.upazila_name == "Raninagar"
    assert {"potato", "sunflower"} <= _names(pools, "Rabi")
    assert pools.k == 3


def test_hl_removes_boro() -> None:
    _, pools = _pools(*RANINAGAR, "HL")
    all_names = set().union(*(_names(pools, season) for season in SEASONS))
    assert not any("boro" in name for name in all_names)


def test_ll_dowarabazar_haor_k_one_boro() -> None:
    _, pools = _pools(*DOWARABAZAR, "LL")
    assert pools.k == 1
    assert pools.flags["haor"] is True
    assert pools.by_season["Rabi"][0].name == "Boro dhan"
    assert pools.by_season["Kharif-1"][0].name == "Fallow"
    assert pools.by_season["Kharif-2"][0].name == "Fallow"


def test_ll_removes_potato_solanaceae_and_cole_crops() -> None:
    _, pools = _pools(*DOWARABAZAR, "LL")
    all_names = set().union(*(_names(pools, season) for season in SEASONS))
    forbidden = {
        "potato",
        "tomato",
        "brinjal",
        "chilli",
        "cabbage",
        "cauliflower",
        "broccoli",
    }
    assert not (all_names & forbidden)


def test_mongla_mhl_only_t_aman() -> None:
    _, pools = _pools(*MONGLA, "MHL")
    assert pools.k == 1
    assert _names(pools, "Rabi") == {"fallow"}
    assert _names(pools, "Kharif-1") == {"fallow"}
    assert _names(pools, "Kharif-2") == {"t. aman dhan"}


def test_high_barind_hl_keeps_chickpea() -> None:
    _, pools = _pools(*CHARGHAT, "HL")
    assert any("chickpea" in name or "gram" in name for name in _names(pools, "Rabi"))


def test_godagari_hl_keeps_chickpea() -> None:
    _, pools = _pools(*GODAGARI, "HL")
    assert any("chickpea" in name or "gram" in name for name in _names(pools, "Rabi"))


def test_ml_is_treated_as_mll() -> None:
    assert canonical_land_type("ml") == "MLL"
    _, pools = _pools(*BELKUCHI, "ML")
    assert pools.k == 2
    assert "jute" in _names(pools, "Kharif-1")


def test_no_empty_season_and_no_unknown_family() -> None:
    for lat, lon in (RANINAGAR, DOWARABAZAR, CHARGHAT, MONGLA):
        for land in ("HL", "MHL", "MLL", "LL"):
            _, pools = _pools(lat, lon, land)
            for season in SEASONS:
                assert pools.by_season[season], (lat, lon, land, season)
                assert all(crop.family != "Unknown" for crop in pools.by_season[season])


def test_charland_fallback_is_deterministic() -> None:
    first = select_candidate_pools([], "MLL", "Sirajganj", SEASONS)
    second = select_candidate_pools([], "MLL", "Sirajganj", SEASONS)

    first_ids = {crop.crop_id for season in SEASONS for crop in first.by_season[season]}
    second_ids = {
        crop.crop_id for season in SEASONS for crop in second.by_season[season]
    }
    assert first_ids == second_ids
    assert first_ids - {"999"} == {str(i) for i in range(5001, 5007)}
    assert first.k == 2
    assert any("alluvial" in warning for warning in first.warnings)


class _FakeHttp:
    """Records calls and returns a recorded BARC payload (or raises)."""

    def __init__(self, payload=None, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[str] = []

    async def get_json(self, url: str, **kwargs) -> object:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        return self.payload


def _copy_db(tmp_path: Path) -> Path:
    path = tmp_path / "barc.db"
    shutil.copy(DB, path)
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "DELETE FROM upazila_suitable_crops WHERE upazila_code = '100419'"
        )
        connection.commit()
    finally:
        connection.close()
    return path


def _payload() -> list[dict]:
    return [
        {
            "crop_id": 11,
            "crop_name": "Potato",
            "crop_season": "Rabi",
            "vs": 1000.0,
            "s": 500.0,
            "ms": 0.0,
        },
        {
            "crop_id": 12,
            "crop_name": "Boro dhan",
            "crop_season": "Rabi",
            "vs": 200.0,
            "s": 0.0,
            "ms": 0.0,
        },
        {
            "crop_id": 13,
            "crop_name": "Mystery Crop",
            "crop_season": "Rabi",
            "vs": 100.0,
            "s": 0.0,
            "ms": 0.0,
        },
    ]


def test_barc_api_fetch_saves_and_then_uses_cache(tmp_path: Path) -> None:
    db = _copy_db(tmp_path)
    http = _FakeHttp(payload=_payload())
    catalog = BarcCatalog(db, http_client=http)

    first = catalog.get_records("100419")
    assert [record["crop_name"] for record in first.records] == [
        "Potato",
        "Boro dhan",
    ]
    assert first.records[0]["effective_area"] == 1350.0
    assert first.source == "barc:api:100419"
    assert any("unknown taxonomy" in warning for warning in first.warnings)

    connection = sqlite3.connect(db)
    try:
        saved = connection.execute(
            "SELECT COUNT(*) FROM upazila_suitable_crops WHERE upazila_code = '100419'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert saved == 2

    second = catalog.get_records("100419")
    assert second.source == "barc:cache:100419"
    assert len(second.records) == 2
    assert len(http.calls) == 1


def test_barc_api_failure_borrows_same_district(tmp_path: Path) -> None:
    db = _copy_db(tmp_path)
    catalog = BarcCatalog(db, http_client=_FakeHttp(error=RuntimeError("offline")))

    result = catalog.get_records("100419")
    assert result.records
    assert result.source.startswith("barc:district:100419<-")
    assert any("unavailable" in warning for warning in result.warnings)


def _environment(lat: float, lon: float, land_type: str) -> Environment:
    return Environment(
        location=Location(latitude=lat, longitude=lon),
        soil=SoilProfile(),
        seasons=[],
        land_type_check=LandTypeCheck(
            farmer_land_type=land_type,
            used_land_type=land_type,
            agreement="match",
        ),
    )


def test_service_bangladesh_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "barc_db", str(DB))
    monkeypatch.setattr(config, "barc_polygons", str(POLYGONS))
    monkeypatch.setattr(config, "adapter_crops", "barc")
    monkeypatch.setitem(config.adapters, "crops", "barc")

    result = run(_environment(*RANINAGAR, "MHL"))
    assert result.supported is True
    assert result.routing["upazila_name"] == "Raninagar"
    assert result.land_type == "MHL"
    assert result.cropping_intensity_k == 3
    assert result.by_season["Rabi"]


def test_service_outside_bangladesh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "barc_polygons", str(POLYGONS))

    result = run(_environment(*NAIROBI, "MHL"))
    assert result.supported is False
    assert result.cropping_intensity_k == 0
    assert all(crops == [] for crops in result.by_season.values())
    assert any("not supported" in warning.lower() for warning in result.warnings)
