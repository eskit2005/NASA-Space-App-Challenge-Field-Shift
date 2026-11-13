"""S4 selection: turn BARC crop records into the small per-season crop pools.

1. Normalize the land type (ML becomes MLL, VLL becomes LL).
2. Drop perennial tree crops and crops that cannot survive the land type.
3. Apply the hard-coded region rules (haor, coastal saline, High Barind).
4. Bucket each season: one champion per plant group (area >= 300 ha), then
   fill the rest by effective area (Rabi 7, Kharif-1 5, Kharif-2 3).
5. Add the alluvial fallback for a charland (MLL) upazila with no data.
6. Compute K from the land-type cap and the number of active seasons.
7. Replace every empty season with a Fallow placeholder (crop_id 999), so no
   downstream stage ever receives an empty list.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cropseq.contracts import Crop

from .taxonomy import is_perennial

HAOR_DISTRICTS = {
    "sunamganj",
    "sylhet",
    "moulvibazar",
    "maulvibazar",
    "habiganj",
    "netrokona",
    "kishoreganj",
    "brahmanbaria",
    "natore",
    "pabna",
}

COASTAL_SALINE_DISTRICTS = {
    "khulna",
    "bagerhat",
    "satkhira",
    "patuakhali",
    "barguna",
    "bhola",
    "noakhali",
    "chittagong",
    "chattogram",
    "coxs bazar",
    "feni",
    "pirojpur",
    "jhalokathi",
    "jhalokati",
}

HIGH_BARIND_DISTRICTS = {
    "rajshahi",
    "chapai nawabganj",
    "nawabganj",
    "naogaon",
}

TARGETS = {"Rabi": 7, "Kharif-1": 5, "Kharif-2": 3}
CHAMPION_MIN_AREA_HA = 300.0

# Fixed ids, names and areas: the same charland always gets the same crops.
CHARLAND_FALLBACK: tuple[dict[str, Any], ...] = (
    {
        "crop_id": 5001,
        "crop_name": "Mustard",
        "season": "Rabi",
        "very_suitable_ha": 5000.0,
        "suitable_ha": 0.0,
        "mod_suitable_ha": 0.0,
        "effective_area": 5000.0,
        "suitability_tier": "Ideal",
        "family": "Brassicaceae",
        "root_type": "medium_tap",
        "is_legume": False,
        "duration_days": 85.0,
        "yield_t_ha": 1.5,
        "land_types": ["HL", "MHL", "MLL"],
    },
    {
        "crop_id": 5002,
        "crop_name": "Groundnut",
        "season": "Rabi",
        "very_suitable_ha": 4500.0,
        "suitable_ha": 0.0,
        "mod_suitable_ha": 0.0,
        "effective_area": 4500.0,
        "suitability_tier": "Ideal",
        "family": "Fabaceae",
        "root_type": "nodulated",
        "is_legume": True,
        "duration_days": 130.0,
        "yield_t_ha": 2.2,
        "land_types": ["HL", "MHL", "MLL"],
    },
    {
        "crop_id": 5003,
        "crop_name": "Grass pea",
        "season": "Rabi",
        "very_suitable_ha": 4000.0,
        "suitable_ha": 0.0,
        "mod_suitable_ha": 0.0,
        "effective_area": 4000.0,
        "suitability_tier": "Ideal",
        "family": "Fabaceae",
        "root_type": "nodulated",
        "is_legume": True,
        "duration_days": 110.0,
        "yield_t_ha": 1.3,
        "land_types": ["HL", "MHL", "MLL"],
    },
    {
        "crop_id": 5004,
        "crop_name": "Wheat",
        "season": "Rabi",
        "very_suitable_ha": 3500.0,
        "suitable_ha": 0.0,
        "mod_suitable_ha": 0.0,
        "effective_area": 3500.0,
        "suitability_tier": "Ideal",
        "family": "Poaceae",
        "root_type": "shallow_fibrous",
        "is_legume": False,
        "duration_days": 110.0,
        "yield_t_ha": 3.8,
        "land_types": ["HL", "MHL", "MLL"],
    },
    {
        "crop_id": 5005,
        "crop_name": "Jute",
        "season": "Kharif-1",
        "very_suitable_ha": 6000.0,
        "suitable_ha": 0.0,
        "mod_suitable_ha": 0.0,
        "effective_area": 6000.0,
        "suitability_tier": "Ideal",
        "family": "Malvaceae",
        "root_type": "deep_tap",
        "is_legume": False,
        "duration_days": 115.0,
        "yield_t_ha": 3.2,
        "land_types": ["HL", "MHL", "MLL"],
    },
    {
        "crop_id": 5006,
        "crop_name": "Sesame",
        "season": "Kharif-1",
        "very_suitable_ha": 4000.0,
        "suitable_ha": 0.0,
        "mod_suitable_ha": 0.0,
        "effective_area": 4000.0,
        "suitability_tier": "Ideal",
        "family": "Pedaliaceae",
        "root_type": "medium_tap",
        "is_legume": False,
        "duration_days": 90.0,
        "yield_t_ha": 1.1,
        "land_types": ["HL", "MHL", "MLL"],
    },
)


@dataclass(frozen=True)
class Candidate:
    crop_id: int
    name: str
    season: str
    family: str
    root_type: str
    is_legume: bool
    duration_days: float
    yield_t_ha: float
    effective_area_ha: float
    tier: str
    score: float
    land_types: tuple[str, ...]


@dataclass
class SelectedPools:
    by_season: dict[str, list[Crop]]
    k: int
    flags: dict[str, bool]
    warnings: list[str]


def canonical_land_type(value: str | None) -> str:
    """ML -> MLL and VLL -> LL; unknown/empty -> MHL."""
    clean = str(value or "").strip().upper()
    if clean == "ML":
        return "MLL"
    if clean == "VLL":
        return "LL"
    return clean if clean in {"HL", "MHL", "MLL", "LL"} else "MHL"


def district_key(value: str | None) -> str:
    """Lowercase, drop apostrophes/periods, collapse whitespace."""
    text = str(value or "").lower().replace("'", "").replace(".", "")
    return " ".join(text.split())


def get_guild(candidate: Candidate) -> str:
    """Plant group used for the diversity champion."""
    name = candidate.name.lower()
    if (
        candidate.is_legume
        or candidate.family == "Fabaceae"
        or any(
            word in name
            for word in (
                "lentil",
                "gram",
                "bean",
                "pea",
                "chickpea",
                "ground nut",
                "groundnut",
                "soybean",
                "cowpea",
            )
        )
    ):
        return "Pulses"
    if any(word in name for word in ("potato", "sweet potato")):
        return "Tubers"
    if any(word in name for word in ("mustard", "sesame", "sunflower", "linseed")):
        return "Oilseeds"
    if any(word in name for word in ("jute", "kenaf", "cotton")):
        return "Fibres"
    if candidate.family == "Poaceae" or any(
        word in name for word in ("rice", "dhan", "wheat", "maize", "barley", "kaon")
    ):
        return "Cereals"
    return "Vegetables"


def _score(candidate_area: float, max_area: float, tier: str) -> float:
    ratio = candidate_area / max_area if max_area > 0 else 0.0
    if tier == "Ideal":
        return round(0.80 + 0.20 * ratio, 2)
    if tier == "Suitable":
        return round(0.55 + 0.24 * ratio, 2)
    return round(0.30 + 0.24 * ratio, 2)


def _sort_key(candidate: Candidate) -> tuple[float, str, int]:
    return (-candidate.effective_area_ha, candidate.name.lower(), candidate.crop_id)


def _deduplicate(pool: list[Candidate]) -> list[Candidate]:
    """Keep the highest-area row for each crop name (BARC has duplicates)."""
    seen: set[str] = set()
    unique: list[Candidate] = []
    for candidate in sorted(pool, key=_sort_key):
        key = candidate.name.lower()
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def _make_candidates(records: list[dict[str, Any]]) -> list[Candidate]:
    """Filter land type/perennials and compute scores."""
    max_area = max((float(r.get("effective_area") or 0) for r in records), default=1.0)
    if max_area <= 0:
        max_area = 1.0

    candidates: list[Candidate] = []
    for record in records:
        name = str(record.get("crop_name") or "").strip()
        family = str(record.get("family") or "")
        if not name or not family or family == "Unknown" or is_perennial(name):
            continue
        land_types = tuple(str(x) for x in record.get("land_types") or [])
        tier = str(record.get("suitability_tier") or "Marginal")
        area = float(record.get("effective_area") or 0)
        candidates.append(
            Candidate(
                crop_id=int(record.get("crop_id") or 0),
                name=name,
                season=str(record.get("season") or ""),
                family=family,
                root_type=str(record.get("root_type") or "medium"),
                is_legume=bool(record.get("is_legume")),
                duration_days=float(record.get("duration_days") or 0),
                yield_t_ha=float(record.get("yield_t_ha") or 0),
                effective_area_ha=area,
                tier=tier,
                score=_score(area, max_area, tier),
                land_types=land_types,
            )
        )
    return candidates


def _eligible(pool: list[Candidate], land_type: str) -> list[Candidate]:
    return [c for c in pool if land_type in c.land_types]


def _bucket(
    pool: list[Candidate],
    target: int,
    *,
    season_name: str,
    land_type: str,
    is_barind: bool,
) -> list[Candidate]:
    """One champion per plant group (>= 300 ha), then fill by area."""
    unique = _deduplicate(pool)
    if not unique or target <= 0:
        return []

    champions: dict[str, Candidate] = {}
    for candidate in unique:
        if candidate.effective_area_ha >= CHAMPION_MIN_AREA_HA:
            champions.setdefault(get_guild(candidate), candidate)

    if is_barind and land_type == "HL" and season_name == "Rabi":
        chickpea = next(
            (
                c
                for c in unique
                if any(term in c.name.lower() for term in ("chickpea", "gram"))
                and c.effective_area_ha > 0
            ),
            None,
        )
        if chickpea is not None:
            champions["Pulses"] = chickpea

    selected = sorted(champions.values(), key=_sort_key)
    selected_names = {c.name.lower() for c in selected}
    for candidate in unique:
        if len(selected) >= target:
            break
        if candidate.name.lower() not in selected_names:
            selected.append(candidate)
            selected_names.add(candidate.name.lower())
    return selected[:target]


def _to_crop(candidate: Candidate) -> Crop:
    return Crop(
        crop_id=str(candidate.crop_id),
        name=candidate.name,
        family=candidate.family,
        attributes={
            "root_type": candidate.root_type,
            "is_legume": candidate.is_legume,
            "duration_days": candidate.duration_days,
            "yield_t_ha": candidate.yield_t_ha,
            "effective_area_ha": candidate.effective_area_ha,
            "suitability_tier": candidate.tier,
            "suitability_score": candidate.score,
            "season": candidate.season,
            "source": "BARC_CZIS",
        },
    )


def _fallow() -> Crop:
    return Crop(
        crop_id="999",
        name="Fallow",
        family="None",
        attributes={
            "root_type": "none",
            "is_legume": False,
            "duration_days": 0.0,
            "yield_t_ha": 0.0,
            "effective_area_ha": 10000.0,
            "suitability_tier": "Ideal",
            "suitability_score": 1.0,
            "season": "Any",
            "source": "FALLOW",
        },
    )


def select_candidate_pools(
    records: list[dict[str, Any]],
    land_type: str | None,
    district_name: str | None,
    season_names: list[str],
) -> SelectedPools:
    """Build the three seasonal pools, K, flags and warnings."""
    used_land = canonical_land_type(land_type)
    district = district_key(district_name)

    is_deep_wetland = used_land == "LL"
    is_haor = is_deep_wetland and district in HAOR_DISTRICTS
    is_coastal = district in COASTAL_SALINE_DISTRICTS
    is_coastal_saline = is_coastal and used_land in {"LL", "MLL"}
    is_barind = district in HIGH_BARIND_DISTRICTS

    warnings: list[str] = []
    pools: dict[str, list[Candidate]] = {name: [] for name in season_names}
    all_candidates = _make_candidates(records)
    for candidate in all_candidates:
        if candidate.season in pools:
            pools[candidate.season].append(candidate)

    for season in season_names:
        pools[season] = _eligible(pools[season], used_land)

    if is_haor:
        rice_words = ("boro", "aman", "deepwater")
        pools["Rabi"] = [
            c for c in pools["Rabi"] if any(w in c.name.lower() for w in rice_words)
        ]
        for season in ("Kharif-1", "Kharif-2"):
            if season in pools:
                pools[season] = []

    coastal_deep = is_coastal_saline and is_deep_wetland
    if coastal_deep:
        for season in ("Rabi", "Kharif-1"):
            if season in pools:
                pools[season] = []
        if "Kharif-2" in pools:
            pools["Kharif-2"] = [
                c for c in pools["Kharif-2"] if "aman" in c.name.lower()
            ]

    if (
        used_land == "MLL"
        and not is_coastal_saline
        and not pools.get("Rabi")
        and not pools.get("Kharif-1")
    ):
        fallback = _make_candidates([dict(row) for row in CHARLAND_FALLBACK])
        for candidate in fallback:
            if candidate.season in pools:
                pools[candidate.season].append(candidate)
        warnings.append(
            "No BARC crop data for this charland upazila; using the alluvial "
            "fallback crop list."
        )

    selected: dict[str, list[Crop]] = {}
    for season in season_names:
        target = TARGETS.get(season, 5)
        if is_haor or (coastal_deep and season == "Kharif-2"):
            target = 1
        elif coastal_deep:
            target = 0
        candidates = _bucket(
            pools[season],
            target,
            season_name=season,
            land_type=used_land,
            is_barind=is_barind,
        )
        selected[season] = [_to_crop(c) for c in candidates]

    if is_haor or coastal_deep:
        k_cap = 1
    elif used_land == "MLL":
        k_cap = 2
    else:
        k_cap = 3

    active_seasons = sum(
        1 for crops in selected.values() if any(crop.crop_id != "999" for crop in crops)
    )
    k = max(1, min(k_cap, active_seasons))

    fallow = _fallow()
    for season in season_names:
        if not selected[season]:
            selected[season] = [fallow]

    return SelectedPools(
        by_season=selected,
        k=k,
        flags={
            "haor": is_haor,
            "coastal_saline": is_coastal_saline,
            "deep_wetland": is_deep_wetland,
        },
        warnings=warnings,
    )
