"""Unit tests for configuration loading and environment overrides."""

import pytest
from cropseq.config import Config


def test_config_defaults() -> None:
    cfg = Config(_env_file=None)
    assert cfg.adapters["soil"] == "fake"
    assert cfg.adapters["weather"] == "fake"
    assert cfg.cache_db == "data/cache.sqlite"


def test_config_env_provider_real(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV_PROVIDER", "real")
    cfg = Config(_env_file=None)
    assert cfg.adapters["soil"] == "soilgrids"
    assert cfg.adapters["weather"] == "openmeteo"


def test_config_adapter_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ADAPTER_SOIL", "soilgrids")
    monkeypatch.setenv("ADAPTER_WEATHER", "fake")
    cfg = Config(_env_file=None)
    assert cfg.adapters["soil"] == "soilgrids"
    assert cfg.adapters["weather"] == "fake"
