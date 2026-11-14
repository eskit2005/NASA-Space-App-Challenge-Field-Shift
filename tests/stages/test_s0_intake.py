"""S0 tests: rules extraction, place lookup, LLM fallback and the API route.

1. Rules tests cover numbers with units, land types and the no-conversion rule.
2. Place tests prove an upazila name routes back to the same upazila in S4.
3. LLM tests inject a fake completer; no real model call is made.
4. Fallback tests prove a missing/broken LLM never crashes the chat.
5. The API test posts s0_input.json to the real FastAPI route.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cropseq.api.main import app
from cropseq.config import config
from cropseq.contracts import FarmerDraft, IntakeMessage, IntakeTurn
from cropseq.stages.s0_intake.adapters.llm import LlmExtractor
from cropseq.stages.s0_intake.draft import merge_fields
from cropseq.stages.s0_intake.places import _load_places, _polygon_path
from cropseq.stages.s0_intake.rules import normalize_land_type
from cropseq.stages.s0_intake.service import run
from cropseq.stages.s4_filtering.router import UpazilaRouter

ROOT = Path(__file__).resolve().parents[2]
POLYGONS = ROOT / "data" / "bangladesh" / "upazila_polygons.json"


def _turn(*messages: str, draft: FarmerDraft | None = None) -> IntakeTurn:
    return IntakeTurn(
        messages=[
            IntakeMessage(role="farmer", content=message) for message in messages
        ],
        draft=draft or FarmerDraft(),
        farm_id="farm-test",
    )


def test_complete_turn_builds_profile() -> None:
    result = run(
        _turn(
            "My farm is in Raninagar, Naogaon. It is 12.5 hectares.",
            "My budget is 8000 USD and I can use 45000 m3 of water. "
            "The land type is MHL.",
        )
    )

    assert result.is_complete is True
    assert result.missing_fields == []
    assert result.profile is not None
    assert result.profile.area_ha == 12.5
    assert result.profile.budget_usd == 8000
    assert result.profile.irrigation_quota_m3 == 45000
    assert result.profile.land_type == "MHL"
    assert result.profile.attributes["upazila"] == "Raninagar"
    assert result.profile.attributes["district"] == "Naogaon"
    assert "hold on" in result.reply.lower()


def test_incomplete_turn_asks_for_the_first_missing_field() -> None:
    result = run(_turn("I have 5 hectares."))

    assert result.is_complete is False
    assert result.draft.area_ha == 5
    assert result.missing_fields[0] == "location"
    assert "where is your farm" in result.reply.lower()
    assert result.profile is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("MHL", "MHL"),
        ("ml", "ML"),
        ("medium low land", "MLL"),
        ("medium-low land", "MLL"),
        ("very low land", "VLL"),
        ("high land", "HL"),
        ("low land", "LL"),
    ],
)
def test_land_type_variants(text: str, expected: str) -> None:
    assert normalize_land_type(text) == expected


def test_place_name_routes_back_to_the_same_upazila() -> None:
    result = run(
        _turn(
            "My farm is in Raninagar, Naogaon. 12.5 hectares. "
            "8000 USD. 45000 m3. Land type MHL."
        )
    )

    assert result.profile is not None
    route = UpazilaRouter(POLYGONS).route(
        result.profile.location.latitude,
        result.profile.location.longitude,
    )
    assert route.upazila_name == "Raninagar"
    assert route.district_name == "Naogaon"


def test_every_upazila_centre_routes_back_to_itself() -> None:
    router = UpazilaRouter(POLYGONS)

    for place in _load_places(_polygon_path()):
        route = router.route(place.latitude, place.longitude)
        assert route.upazila_code == place.code, place.upazila


def test_later_message_overrides_an_earlier_value() -> None:
    result = run(_turn("I have 12 hectares.", "Actually, 15 hectares."))

    assert result.draft.area_ha == 15


def test_place_correction_replaces_coordinates() -> None:
    result = run(
        _turn(
            "My farm is at 24.78, 89.04. 12.5 hectares. 8000 USD. "
            "45000 m3. Land type MHL.",
            "Actually it is in Raninagar, Naogaon.",
        )
    )

    assert result.profile is not None
    route = UpazilaRouter(POLYGONS).route(
        result.profile.location.latitude,
        result.profile.location.longitude,
    )
    assert route.upazila_name == "Raninagar"


def test_unknown_place_does_not_invent_a_location() -> None:
    result = run(
        _turn("My farm is in Atlantis. 12 hectares. 8000 USD. 45000 m3. Land type MHL.")
    )

    assert result.draft.location is None
    assert result.missing_fields == ["location"]
    assert any(
        "could not find upazila" in warning.lower() for warning in result.warnings
    )


def test_budget_in_taka_is_not_converted() -> None:
    result = run(_turn("My budget is 50000 taka."))

    assert result.draft.budget_usd is None


def test_area_in_acres_is_not_converted() -> None:
    result = run(_turn("I have 5 acres."))

    assert result.draft.area_ha is None


def test_llm_disabled_uses_rules_with_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(config.adapters, "intake", "llm")
    monkeypatch.setattr(config, "llm_enabled", False)

    result = run(
        _turn(
            "My farm is in Raninagar, Naogaon. 12.5 hectares. "
            "8000 USD. 45000 m3. Land type MHL."
        )
    )

    assert result.is_complete is True
    assert any("LLM_ENABLED" in warning for warning in result.warnings)


def test_llm_failure_falls_back_to_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(config.adapters, "intake", "llm")
    monkeypatch.setattr(config, "llm_enabled", True)

    def _fail(self, messages, draft):
        raise RuntimeError("offline")

    monkeypatch.setattr(LlmExtractor, "extract", _fail)

    result = run(
        _turn(
            "My farm is in Raninagar, Naogaon. 12.5 hectares. "
            "8000 USD. 45000 m3. Land type MHL."
        )
    )

    assert result.is_complete is True
    assert any("rule-based" in warning for warning in result.warnings)


def test_llm_adapter_parses_fenced_json() -> None:
    seen: list[str] = []

    def _complete(system: str, user: str) -> str:
        seen.append(user)
        return '```json\n{"fields": {"area_ha": 3, "land_type": "ML"}, "reply": "Got it."}\n```'

    extractor = LlmExtractor(completer=_complete)
    result = extractor.extract([], FarmerDraft())

    assert result.fields == {"area_ha": 3, "land_type": "ML"}
    assert result.reply == "Got it."
    assert "Missing required fields" in seen[0]


def test_priorities_are_merged_and_unknown_keys_are_dropped() -> None:
    draft, _ = merge_fields(
        FarmerDraft(),
        {"priorities": {"gross_margin": 0.7, "water_m3": 0.3, "bad_key": 1.0}},
    )

    assert draft.priorities == {"gross_margin": 0.7, "water_m3": 0.3}


def test_same_turn_is_deterministic() -> None:
    turn = _turn(
        "My farm is in Raninagar, Naogaon. 12.5 hectares. "
        "8000 USD. 45000 m3. Land type MHL."
    )

    first = run(turn).model_dump()
    second = run(turn).model_dump()

    assert first == second


def test_intake_api_route() -> None:
    payload = json.loads(
        (ROOT / "data" / "data_shape" / "s0_input.json").read_text(encoding="utf-8")
    )
    client = TestClient(app)

    response = client.post("/api/v1/intake/message", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["is_complete"] is True
    assert body["profile"]["area_ha"] == 12.5
    assert body["source"].startswith("S0 intake")


def test_intake_extracts_soil_ph_and_irrigation_method() -> None:
    turn = _turn(
        "My farm is in Raninagar, Naogaon. 12.5 hectares. "
        "8000 USD. 45000 m3. Land type MHL. "
        "My lab soil pH is 6.5 and irrigation is tube well."
    )
    result = run(turn)
    assert result.is_complete is True
    assert result.profile is not None
    assert result.profile.soil_overrides == {"ph": 6.5}
    assert result.profile.attributes["irrigation_method"] == "tube_well"


def test_post_completion_update_soil_ph_and_irrigation_method() -> None:
    turn1 = _turn(
        "My farm is in Raninagar, Naogaon. 12.5 hectares. "
        "8000 USD. 45000 m3. Land type MHL."
    )
    result1 = run(turn1)
    assert result1.is_complete is True
    assert result1.profile.soil_overrides == {}

    # Now add soil pH and irrigation method in follow-up turn
    turn2 = IntakeTurn(
        messages=[
            *turn1.messages,
            IntakeMessage(role="assistant", content=result1.reply),
            IntakeMessage(role="farmer", content="My lab soil pH is 6.2 and irrigation method is canal."),
        ],
        draft=result1.draft,
        farm_id=result1.profile.farm_id,
    )
    result2 = run(turn2)
    assert result2.is_complete is True
    assert result2.profile.soil_overrides == {"ph": 6.2}
    assert result2.profile.attributes["irrigation_method"] == "canal"
    assert "soil pH to 6.2" in result2.reply
    assert "irrigation method to canal" in result2.reply

