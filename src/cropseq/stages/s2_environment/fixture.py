"""Shared fixture loader for S2 (stub payloads live in data/data_shape)."""

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[4] / "data" / "data_shape" / "s2_output.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))
