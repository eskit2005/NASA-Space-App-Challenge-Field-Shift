"""Shared fixture loader for S4 (stub data lives in data/data_shape)."""

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[4] / "data" / "data_shape" / "s4_output.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
