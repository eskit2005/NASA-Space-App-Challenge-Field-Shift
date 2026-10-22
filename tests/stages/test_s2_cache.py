"""Unit tests for S2 SQLite cache and key generation."""

from pathlib import Path
from cropseq.stages.s2_environment.cache.sqlite import SQLiteCache, make_cache_key


def test_make_cache_key_deterministic() -> None:
    req_a = {"latitude": 23.8, "longitude": 90.4}
    req_b = {"longitude": 90.4, "latitude": 23.8}
    key_a = make_cache_key("soilgrids", req_a)
    key_b = make_cache_key("soilgrids", req_b)
    assert key_a == key_b
    assert len(key_a) == 64


def test_make_cache_key_different_provider_or_params() -> None:
    key1 = make_cache_key("soilgrids", {"lat": 23.8})
    key2 = make_cache_key("open_meteo", {"lat": 23.8})
    key3 = make_cache_key("soilgrids", {"lat": 24.0})
    assert key1 != key2
    assert key1 != key3


def test_sqlite_cache_lifecycle(tmp_path: Path) -> None:
    db_path = tmp_path / "test_cache.sqlite"
    cache = SQLiteCache(db_path)

    key = make_cache_key("test_provider", {"foo": "bar"})
    assert cache.get(key) is None

    test_payload = {"status": "ok", "value": 42}
    cache.set(key, "test_provider", {"foo": "bar"}, test_payload)

    retrieved = cache.get(key)
    assert retrieved == test_payload

    # Overwrite / update
    updated_payload = {"status": "updated", "value": 100}
    cache.set(key, "test_provider", {"foo": "bar"}, updated_payload)
    assert cache.get(key) == updated_payload

    cache.close()
