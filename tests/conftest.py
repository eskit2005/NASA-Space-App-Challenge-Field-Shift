"""Shared pytest fixtures and test environment setup."""

import pytest

from cropseq.config import config


@pytest.fixture(autouse=True)
def isolated_test_config(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Ensure all tests run offline with fake adapters and isolated cache by default."""
    monkeypatch.setattr(
        config,
        "adapters",
        {
            "soil": "fake",
            "weather": "fake",
            "crops": "fake",
            "explainer": "fake",
        },
    )
    test_db = str(tmp_path / "test_cache.sqlite")
    monkeypatch.setattr(config, "cache_db", test_db)
