"""Unit tests for configuration loading and environment overrides."""

from cropseq.config import Config


def test_config_defaults() -> None:
    cfg = Config(_env_file=None)
    assert cfg.adapters["soil"] == "soilgrids"
    assert cfg.adapters["weather"] == "openmeteo,nasa_power"
    assert cfg.adapters["crops"] == "barc"
    assert cfg.adapters["intake"] == "rules"
    assert cfg.cache_db == "data/cache.sqlite"
    assert cfg.barc_db == "data/bangladesh/crop_recommender.db"
    assert cfg.barc_polygons == "data/bangladesh/upazila_polygons.json"
    assert cfg.barc_centres == "data/bangladesh/upazila_centres.json"
    assert cfg.max_sequences == 60
    assert cfg.crop_params == "data/crops/crop_params.json"
    assert cfg.api_key == ""
    assert "localhost:3000" in cfg.cors_origins


def test_config_adapter_override(monkeypatch) -> None:
    monkeypatch.setenv("ADAPTER_SOIL", "custom")
    cfg = Config(_env_file=None)
    assert cfg.adapters["soil"] == "custom"
