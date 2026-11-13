"""S0 place lookup: turn an upazila name into a usable farm coordinate.

1. Load the same 505-upazila boundary file that S4 uses.
2. For each upazila, find a deterministic point INSIDE its polygon with no
   other upazila overlapping it.
3. Save those points once to data/bangladesh/upazila_centres.json; runtime
   reads that small file. Regenerate with:
   `uv run python -m cropseq.stages.s0_intake.places`
4. Index upazilas by normalized name (and name + district).
5. Resolve a farmer's place name to that point, or return None if ambiguous.
6. Also scan free text for known upazila and district names (rules adapter).

Why a point inside the polygon: S4 routes a coordinate to an upazila. Using a
point inside the named upazila means S4 routes back to the same upazila. The
point is an approximation of the farm location and is labelled as such.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from cropseq.config import config


@dataclass(frozen=True)
class Place:
    """One upazila and a representative point inside it."""

    code: str
    upazila: str
    district: str
    division: str
    latitude: float
    longitude: float


def normalize_name(value: str | None) -> str:
    """Lowercase, drop punctuation and common suffixes, collapse spaces."""
    text = str(value or "").lower().replace("'", "").replace(".", "")
    text = re.sub(r"\b(upazila|upazilla|thana)\b", " ", text)
    return " ".join(text.split())


def _polygon_path(polygons_path: str | Path | None = None) -> str:
    path = Path(polygons_path or config.barc_polygons)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[4] / path
    return str(path)


def point_in_ring(lat: float, lon: float, ring: list[list[float]]) -> bool:
    """Ray casting: is (lat, lon) inside one ring of [lon, lat] points?"""
    inside = False
    n = len(ring)
    if n < 3:
        return False

    p1x, p1y = ring[0][0], ring[0][1]
    for i in range(1, n + 1):
        p2x, p2y = ring[i % n][0], ring[i % n][1]
        if min(p1y, p2y) < lat <= max(p1y, p2y) and lon <= max(p1x, p2x):
            if p1y != p2y:
                xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
            else:
                xinters = p1x
            if p1x == p2x or lon <= xinters:
                inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def _inside_polygon(lat: float, lon: float, polygon: list[list[list[float]]]) -> bool:
    if not polygon or not polygon[0]:
        return False
    if not point_in_ring(lat, lon, polygon[0]):
        return False
    return not any(point_in_ring(lat, lon, hole) for hole in polygon[1:])


def _bbox(coords: Any) -> tuple[float, float, float, float]:
    """Return (min_lat, max_lat, min_lon, max_lon) for nested coordinates."""
    min_lat = min_lon = float("inf")
    max_lat = max_lon = float("-inf")
    stack = [coords]
    while stack:
        node = stack.pop()
        if (
            isinstance(node, (list, tuple))
            and len(node) == 2
            and all(isinstance(v, (int, float)) for v in node)
        ):
            lon, lat = float(node[0]), float(node[1])
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
    if min_lat == float("inf"):
        return 0.0, 0.0, 0.0, 0.0
    return min_lat, max_lat, min_lon, max_lon


def _area_centroid(ring: list[list[float]]) -> tuple[float, float] | None:
    """Area centroid of a [lon, lat] ring, or None for a degenerate ring."""
    n = len(ring)
    if n < 3:
        return None
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        x0, y0 = ring[i][0], ring[i][1]
        x1, y1 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area2) < 1e-12:
        return None
    return cx / (3.0 * area2), cy / (3.0 * area2)


def _largest_polygon(
    polygons: list[list[list[list[float]]]],
) -> list[list[list[float]]] | None:
    """Return the polygon with the largest bounding box."""
    best: list[list[list[float]]] | None = None
    best_area = -1.0
    for polygon in polygons:
        if not polygon or not polygon[0]:
            continue
        all_points = [point for ring in polygon for point in ring]
        if not all_points:
            continue
        min_lat, max_lat, min_lon, max_lon = _bbox(all_points)
        area = (max_lat - min_lat) * (max_lon - min_lon)
        if area > best_area:
            best_area = area
            best = polygon
    return best


def _candidate_points(
    polygon: list[list[list[float]]],
) -> list[tuple[float, float]]:
    """Deterministic candidate points, starting with the bbox centre."""
    if not polygon or not polygon[0]:
        return []
    min_lat, max_lat, min_lon, max_lon = _bbox(polygon[0])
    candidates: list[tuple[float, float]] = [
        ((min_lat + max_lat) / 2.0, (min_lon + max_lon) / 2.0)
    ]
    centroid = _area_centroid(polygon[0])
    if centroid is not None:
        candidates.append((centroid[1], centroid[0]))
    for i in range(1, 7):
        for j in range(1, 7):
            lon = min_lon + (max_lon - min_lon) * i / 7.0
            lat = min_lat + (max_lat - min_lat) * j / 7.0
            candidates.append((lat, lon))
    return candidates


def _overlaps_another(
    latitude: float,
    longitude: float,
    record: dict[str, Any],
    records: list[dict[str, Any]],
) -> bool:
    """True if the point also falls inside a different upazila polygon."""
    for other in records:
        if other is record:
            continue
        min_lat, max_lat, min_lon, max_lon = other["bbox"]
        if not (min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon):
            continue
        if any(
            _inside_polygon(latitude, longitude, polygon)
            for polygon in other["polygons"]
        ):
            return True
    return False


def _choose_point(
    record: dict[str, Any],
    records: list[dict[str, Any]],
) -> tuple[float, float] | None:
    """Pick a point inside this upazila that no other upazila also claims."""
    polygon = record["polygon"]
    inside_own = [
        point
        for point in record["candidates"]
        if _inside_polygon(point[0], point[1], polygon)
    ]
    if not inside_own:
        return record["candidates"][0] if record["candidates"] else None
    for latitude, longitude in inside_own:
        if not _overlaps_another(latitude, longitude, record, records):
            return latitude, longitude
    # Overlapping boundaries: the first point inside the named upazila is the
    # best deterministic answer. S4 may still route it to the neighbour.
    return inside_own[0]


def _centres_path() -> Path:
    """Path of the small derived file that caches the safe points."""
    path = Path(config.barc_centres)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[4] / path
    return path


def _read_centres(path: Path) -> tuple[Place, ...]:
    """Read the derived centres file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    places: list[Place] = []
    for row in data.get("places", []):
        places.append(
            Place(
                code=str(row["code"]),
                upazila=str(row["upazila"]),
                district=str(row["district"]),
                division=str(row["division"]),
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
        )
    return tuple(places)


@lru_cache(maxsize=2)
def _load_places(path: str) -> tuple[Place, ...]:
    """Load the small derived centres file, or compute it once if missing."""
    try:
        return _read_centres(_centres_path())
    except OSError, json.JSONDecodeError, KeyError, TypeError, ValueError:
        return _compute_places(path)


def _compute_places(path: str) -> tuple[Place, ...]:
    """Compute safe points from the polygon file. Slow; used to build the cache."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return ()

    records: list[dict[str, Any]] = []
    for feature in data.get("features", []):
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        if not coords:
            continue
        polygons = coords if geometry.get("type") == "MultiPolygon" else [coords]
        polygon = _largest_polygon(polygons)
        if polygon is None:
            continue
        records.append(
            {
                "code": str(properties.get("geocode") or properties.get("id") or ""),
                "upazila": str(properties.get("upazila") or "Unknown"),
                "district": str(properties.get("district") or ""),
                "division": str(properties.get("division") or ""),
                "bbox": _bbox(coords),
                "polygon": polygon,
                "polygons": polygons,
                "candidates": _candidate_points(polygon),
            }
        )

    places: list[Place] = []
    for record in records:
        point = _choose_point(record, records)
        if point is None:
            continue
        places.append(
            Place(
                code=record["code"],
                upazila=record["upazila"],
                district=record["district"],
                division=record["division"],
                latitude=point[0],
                longitude=point[1],
            )
        )
    return tuple(places)


@lru_cache(maxsize=2)
def _index(
    path: str,
) -> tuple[
    dict[str, list[Place]],
    dict[str, Place],
    tuple[str, ...],
]:
    """Build name -> places, 'name district' -> place, and district names."""
    by_name: dict[str, list[Place]] = {}
    by_full: dict[str, Place] = {}
    districts: set[str] = set()
    for place in _load_places(path):
        name = normalize_name(place.upazila)
        district = normalize_name(place.district)
        by_name.setdefault(name, []).append(place)
        by_full[f"{name} {district}"] = place
        districts.add(district)
    return by_name, by_full, tuple(sorted(districts))


def resolve_place(
    name: str | None,
    district: str | None = None,
    polygons_path: str | Path | None = None,
) -> Place | None:
    """Resolve an upazila name to a place. None if unknown or ambiguous."""
    raw = normalize_name(name)
    if not raw:
        return None

    path = _polygon_path(polygons_path)
    by_name, by_full, _ = _index(path)
    wanted_district = normalize_name(district)

    candidates = by_name.get(raw, [])
    if wanted_district:
        candidates = [
            place
            for place in candidates
            if normalize_name(place.district) == wanted_district
        ]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return None

    if wanted_district and f"{raw} {wanted_district}" in by_full:
        return by_full[f"{raw} {wanted_district}"]

    # Support "Raninagar, Naogaon".
    parts = [normalize_name(part) for part in str(name).split(",")]
    parts = [part for part in parts if part]
    if len(parts) >= 2:
        return resolve_place(parts[0], parts[1], polygons_path)

    return None


def find_place_names(
    text: str,
    polygons_path: str | Path | None = None,
) -> list[str]:
    """Return normalized upazila names that appear in the text."""
    normalized = normalize_name(text)
    by_name, _, _ = _index(_polygon_path(polygons_path))
    matches = [
        name
        for name in by_name
        if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", normalized)
    ]
    # Prefer the longest match: "naogaon sadar" over "naogaon".
    return sorted(matches, key=len, reverse=True)


def find_districts_in_text(
    text: str,
    polygons_path: str | Path | None = None,
) -> list[str]:
    """Return normalized district names that appear in the text."""
    normalized = normalize_name(text)
    _, _, districts = _index(_polygon_path(polygons_path))
    return [
        district
        for district in districts
        if re.search(rf"(?<![a-z0-9]){re.escape(district)}(?![a-z0-9])", normalized)
    ]


if __name__ == "__main__":
    polygon_file = _polygon_path()
    computed = _compute_places(polygon_file)
    output_file = _centres_path()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": f"derived from {polygon_file}",
        "count": len(computed),
        "places": [asdict(place) for place in computed],
    }
    output_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(computed)} upazila centres to {output_file}")
