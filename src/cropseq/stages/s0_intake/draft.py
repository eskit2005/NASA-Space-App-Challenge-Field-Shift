"""S0 draft handling: merge new facts into the profile and validate it.

1. `missing_fields` lists what the farmer still has to answer, in ask order.
2. `merge_fields` copies only valid, explicitly given values into the draft.
3. Nothing is guessed: a bad or missing value leaves the old draft unchanged.
4. A place name is resolved to a point inside that upazila (S0 places.py).
5. `build_profile` produces the exact FarmerProfile for the optimize endpoint.
6. If the farmer never sent a farm_id, S0 derives a stable id from the location.
"""

from __future__ import annotations

import hashlib
from typing import Any

from pydantic import ValidationError

from cropseq.config import config
from cropseq.contracts import FarmerDraft, FarmerProfile, IntakeTurn
from cropseq.errors import InvalidInput

from .places import resolve_place
from .rules import normalize_land_type, to_float

REQUIRED_FIELDS: tuple[str, ...] = (
    "location",
    "area_ha",
    "budget_usd",
    "irrigation_quota_m3",
    "land_type",
)


def missing_fields(draft: FarmerDraft) -> list[str]:
    """Return the required fields that are still empty."""
    missing: list[str] = []
    if draft.location is None:
        missing.append("location")
    if draft.area_ha is None:
        missing.append("area_ha")
    if draft.budget_usd is None:
        missing.append("budget_usd")
    if draft.irrigation_quota_m3 is None:
        missing.append("irrigation_quota_m3")
    if draft.land_type is None:
        missing.append("land_type")
    return missing


def _set_number(
    data: dict[str, Any],
    fields: dict[str, Any],
    key: str,
    warnings: list[str],
    *,
    positive: bool = False,
) -> None:
    if fields.get(key) is None:
        return
    value = to_float(fields[key])
    if value is None:
        warnings.append(f"Ignored {key}: the value was not a number.")
        return
    if positive and value <= 0:
        warnings.append(f"Ignored {key}: the value must be greater than zero.")
        return
    if not positive and value < 0:
        warnings.append(f"Ignored {key}: the value cannot be negative.")
        return
    data[key] = value


def _merge_location(
    data: dict[str, Any],
    fields: dict[str, Any],
    warnings: list[str],
) -> None:
    latitude = to_float(fields.get("latitude"))
    longitude = to_float(fields.get("longitude"))
    if latitude is not None and longitude is not None:
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            data["location"] = {"latitude": latitude, "longitude": longitude}
            attributes = data.setdefault("attributes", {})
            attributes.pop("location_source", None)
            return
        warnings.append("Ignored coordinates: values are outside the valid range.")
        return

    location = fields.get("location")
    if isinstance(location, dict):
        _merge_location(data, location, warnings)
        return

    place_name = fields.get("place_name")
    if not place_name:
        return

    district = fields.get("district")
    place = resolve_place(
        str(place_name),
        str(district) if district is not None else None,
    )
    if place is None:
        warnings.append(
            f"Could not find upazila '{place_name}'. Please give the upazila "
            "name or the latitude and longitude."
        )
        return

    data["location"] = {
        "latitude": place.latitude,
        "longitude": place.longitude,
    }
    attributes = data.setdefault("attributes", {})
    attributes["upazila"] = place.upazila
    attributes["district"] = place.district
    if attributes.get("location_source") != "upazila_centre":
        warnings.append(
            f"Farm location approximated from the centre of {place.upazila} upazila."
        )
    attributes["location_source"] = "upazila_centre"


def _merge_priorities(
    data: dict[str, Any],
    fields: dict[str, Any],
) -> None:
    priorities = fields.get("priorities")
    if not isinstance(priorities, dict):
        return
    merged = dict(data.get("priorities") or {})
    for key, value in priorities.items():
        if key not in config.objectives:
            continue
        number = to_float(value)
        if number is not None and number >= 0:
            merged[key] = number
    data["priorities"] = merged


def _merge_soil(
    data: dict[str, Any],
    fields: dict[str, Any],
    warnings: list[str],
) -> None:
    merged = dict(data.get("soil_overrides") or {})
    overrides = fields.get("soil_overrides")
    if isinstance(overrides, dict):
        for key, value in overrides.items():
            number = to_float(value)
            if number is not None:
                merged[str(key)] = number

    ph = to_float(fields.get("soil_ph"))
    if ph is not None:
        if 0 <= ph <= 14:
            merged["ph"] = ph
        else:
            warnings.append("Ignored soil pH: it must be between 0 and 14.")
    data["soil_overrides"] = merged


def _merge_attributes(data: dict[str, Any], fields: dict[str, Any]) -> None:
    attributes = data.setdefault("attributes", {})
    resolved_place = attributes.get("location_source") == "upazila_centre"
    for key in ("district", "upazila", "irrigation_method"):
        # Do not replace the canonical district/upazila names set from the
        # boundary file with the normalized text the farmer typed.
        if key in {"district", "upazila"} and resolved_place:
            continue
        value = fields.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            attributes[key] = value

    custom = fields.get("attributes")
    if isinstance(custom, dict):
        for key, value in custom.items():
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                attributes[str(key)] = value


def merge_fields(
    draft: FarmerDraft,
    fields: dict[str, Any],
) -> tuple[FarmerDraft, list[str]]:
    """Merge extracted fields into the draft. Invalid values are skipped."""
    data = draft.model_dump()
    data.setdefault("priorities", {})
    data.setdefault("soil_overrides", {})
    data.setdefault("attributes", {})
    warnings: list[str] = []

    _merge_location(data, fields, warnings)
    _set_number(data, fields, "area_ha", warnings, positive=True)
    _set_number(data, fields, "budget_usd", warnings)
    _set_number(data, fields, "irrigation_quota_m3", warnings)

    if fields.get("land_type") is not None:
        land_type = normalize_land_type(fields["land_type"])
        if land_type is None:
            warnings.append("Ignored land type: use HL, MHL, MLL, LL or VLL.")
        else:
            data["land_type"] = land_type

    _merge_priorities(data, fields)
    _merge_soil(data, fields, warnings)
    _merge_attributes(data, fields)

    try:
        return FarmerDraft.model_validate(data), warnings
    except ValidationError as exc:
        warnings.append(f"Ignored invalid profile value: {exc.errors()[0]['msg']}")
        return draft, warnings


def _derived_farm_id(draft: FarmerDraft) -> str:
    """Stable id from the location, so the same farm always gets the same id."""
    if draft.location is None:
        return "farm-pending"
    key = f"{draft.location.latitude:.5f},{draft.location.longitude:.5f}"
    return "farm-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def build_profile(turn: IntakeTurn, draft: FarmerDraft) -> FarmerProfile:
    """Build the exact FarmerProfile once every required field is present."""
    missing = missing_fields(draft)
    if missing:
        raise InvalidInput(f"Cannot build a profile; missing: {', '.join(missing)}")

    if (
        draft.location is None
        or draft.area_ha is None
        or draft.budget_usd is None
        or draft.irrigation_quota_m3 is None
    ):
        raise InvalidInput("Cannot build a profile; a required value is missing.")

    farm_id = (turn.farm_id or "").strip() or _derived_farm_id(draft)
    return FarmerProfile(
        farm_id=farm_id,
        location=draft.location,
        area_ha=draft.area_ha,
        budget_usd=draft.budget_usd,
        irrigation_quota_m3=draft.irrigation_quota_m3,
        land_type=draft.land_type or "MHL",
        priorities=draft.priorities,
        soil_overrides=draft.soil_overrides,
        attributes=draft.attributes,
    )
