"""S0 rules adapter: deterministic extraction when the LLM is unavailable.

1. Scan every farmer message, in order, so the latest correction wins.
2. Pull out coordinates, upazila/district names, numbers with units, land
   type, soil pH and irrigation method.
3. Never guess a missing value and never convert currencies or land units.
4. Return only the fields that were found. service.py merges them with the
   existing draft and decides what is still missing.
"""

from __future__ import annotations

import re
from typing import Any

from cropseq.contracts import IntakeMessage

from .places import find_districts_in_text, find_place_names

NUMBER = r"(\d[\d,]*(?:\.\d+)?)"

LAND_PHRASES: tuple[tuple[str, str], ...] = (
    ("very low land", "VLL"),
    ("very lowland", "VLL"),
    ("very low", "VLL"),
    ("medium low land", "MLL"),
    ("medium lowland", "MLL"),
    ("medium-low land", "MLL"),
    ("medium-lowland", "MLL"),
    ("medium-low", "MLL"),
    ("medium low", "MLL"),
    ("medium high land", "MHL"),
    ("medium highland", "MHL"),
    ("medium-high land", "MHL"),
    ("medium-highland", "MHL"),
    ("medium-high", "MHL"),
    ("medium high", "MHL"),
    ("high land", "HL"),
    ("highland", "HL"),
    ("low land", "LL"),
    ("lowland", "LL"),
)

IRRIGATION_METHODS: tuple[tuple[str, str], ...] = (
    ("deep tube", "deep_tube_well"),
    ("shallow tube", "shallow_tube_well"),
    ("tube well", "tube_well"),
    ("tubewell", "tube_well"),
    ("canal", "canal"),
    ("pond", "pond"),
    ("rain-fed", "rainfed"),
    ("rainfed", "rainfed"),
)


def to_float(value: Any) -> float | None:
    """Best-effort number from a model value like '12.5 ha' or '$8,000'."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", value.strip().replace(",", ""))
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_land_type(value: Any) -> str | None:
    """Map common land-type words to HL/MHL/MLL/LL/VLL/ML."""
    text = str(value or "").strip().lower()
    code = text.upper()
    if code in {"HL", "MHL", "MLL", "LL", "VLL", "ML"}:
        return code
    for phrase, mapped in LAND_PHRASES:
        if phrase in text:
            return mapped
    return None


def _coordinates(text: str) -> tuple[float, float] | None:
    """Find a labelled pair or a plausible Bangladesh coordinate pair."""
    labelled = re.search(
        rf"lat(?:itude)?\s*[:=]?\s*{NUMBER}.*?"
        rf"lon(?:gitude)?\s*[:=]?\s*{NUMBER}",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if labelled:
        return float(labelled.group(1).replace(",", "")), float(
            labelled.group(2).replace(",", "")
        )

    for match in re.finditer(r"(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)", text):
        latitude = float(match.group(1))
        longitude = float(match.group(2))
        if 20.5 <= latitude <= 26.7 and 88.0 <= longitude <= 92.7:
            return latitude, longitude
    return None


def _land_type(text: str) -> str | None:
    """Match explicit codes or land-type words."""
    cleaned = text.strip().lower()
    for phrase, mapped in LAND_PHRASES:
        if phrase in cleaned:
            return mapped
    # Match standalone or contextual codes e.g. "MHL", "HL", "land type: MHL"
    match = re.search(r"\b(hl|mhl|mll|ll|vll|ml)\b", cleaned)
    if match:
        return match.group(1).upper()
    return None


def _irrigation_method(text: str) -> str | None:
    for phrase, code in IRRIGATION_METHODS:
        if phrase in text:
            return code
    return None


def extract_fields(messages: list[IntakeMessage]) -> dict[str, Any]:
    """Extract fields from farmer messages. Later messages overwrite earlier."""
    fields: dict[str, Any] = {}

    for message in messages:
        if message.role != "farmer":
            continue
        text = message.content.strip().lower()
        if not text:
            continue

        coordinates = _coordinates(text)
        if coordinates is not None:
            fields["latitude"], fields["longitude"] = coordinates
            fields.pop("place_name", None)
            fields.pop("district", None)
        else:
            places = find_place_names(message.content)
            districts = find_districts_in_text(message.content)
            if places:
                fields["place_name"] = places[0]
                fields.pop("latitude", None)
                fields.pop("longitude", None)
            else:
                # Keep an unknown place name so service.py can warn the farmer
                # instead of silently pretending nothing was said.
                spoken = re.search(
                    r"\b(?:farm\s+is\s+in|farm\s+is\s+at|i\s+am\s+in|"
                    r"located\s+in|village|upazila)\s+([a-z][a-z '-]{1,30})",
                    text,
                )
                if spoken:
                    fields["place_name"] = spoken.group(1).strip()
                    fields.pop("latitude", None)
                    fields.pop("longitude", None)
            if districts:
                fields["district"] = districts[0]

        area = re.search(rf"\b{NUMBER}\s*(?:hectares?|ha)\b", text)
        if area:
            fields["area_ha"] = float(area.group(1).replace(",", ""))

        budget = re.search(rf"(?:us\$|usd|\$)\s*{NUMBER}", text)
        if budget is None:
            budget = re.search(
                rf"\b{NUMBER}\s*(?:usd|dollars?|bucks)\b",
                text,
            )
        if budget:
            fields["budget_usd"] = float(budget.group(1).replace(",", ""))

        water = re.search(
            rf"\b{NUMBER}\s*(?:m3|m³|cubic\s*met(?:er|re)s?|cum)\b",
            text,
        )
        if water:
            fields["irrigation_quota_m3"] = float(water.group(1).replace(",", ""))

        land_type = _land_type(text)
        if land_type is not None:
            fields["land_type"] = land_type

        ph = re.search(rf"\bph\s*(?:is|:|=|of)?\s*{NUMBER}\b", text)
        if ph:
            fields["soil_ph"] = float(ph.group(1).replace(",", ""))

        method = _irrigation_method(text)
        if method is not None:
            fields["irrigation_method"] = method

    return fields
