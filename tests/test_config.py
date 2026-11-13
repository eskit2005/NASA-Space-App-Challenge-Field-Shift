"""Unit tests for configuration loading and environment overrides."""

from cropseq.config import Config


def test_config_defaults() -> None:
    cfg = Config(_env_file=None)
    assert cfg.adapters["soil"] == "soilgrids"
    assert cfg.adapters["weather"] == "openmeteo"
    assert cfg.cache_db == "data/cache.sqlite"


def test_config_adapter_override(monkeypatch) -> None:
    monkeypatch.setenv("ADAPTER_SOIL", "custom")
    cfg = Config(_env_file=None)
    assert cfg.adapters["soil"] == "custom"
