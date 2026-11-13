"""Shared pytest fixtures and test environment setup."""

import pytest

from cropseq.config import config


@pytest.fixture(autouse=True)
def isolated_test_cache(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Point the cache at a temp file so tests never touch data/cache.sqlite."""
    monkeypatch.setattr(config, "cache_db", str(tmp_path / "test_cache.sqlite"))
