"""S4 routing: match a farm coordinate to one of the 505 Bangladesh upazilas.

1. Reject points outside the national envelope (20.50-26.70 N, 88.00-92.70 E).
2. Keep only upazilas whose bounding box contains the point (fast prefilter).
3. Run a point-in-polygon test on each candidate (ray casting, holes respected).
4. If the point is just outside every polygon, use the nearest candidate centre.
5. Return the upazila code, name, district and division for S4.
6. The latency and candidate count are not part of the routing output, so the
   same coordinate always produces the same result.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

BD_MIN_LAT = 20.50
BD_MAX_LAT = 26.70
BD_MIN_LON = 88.00
BD_MAX_LON = 92.70

POLYGONS_FILE = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "bangladesh"
    / "upazila_polygons.json"
)


@dataclass(frozen=True)
class RouteDecision:
    """Where a coordinate falls, in the form S4 needs."""

    is_bangladesh: bool
    upazila_code: str | None
    upazila_name: str | None
    district_name: str | None
    division_name: str | None
    method: str
    candidates_count: int

    def to_dict(self) -> dict[str, str | int | bool | None]:
        return asdict(self)


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


def point_in_polygon(lat: float, lon: float, polygon: list[list[list[float]]]) -> bool:
    """Inside the outer ring and not inside any hole."""
    if not polygon or not polygon[0]:
        return False
    if not point_in_ring(lat, lon, polygon[0]):
        return False
    return not any(point_in_ring(lat, lon, hole) for hole in polygon[1:])


def _extract_bbox(coords: Any) -> tuple[float, float, float, float]:
    """Return (min_lat, max_lat, min_lon, max_lon) for any nested coordinate list."""
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


@lru_cache(maxsize=2)
def _load_upazilas(path: str) -> tuple[dict[str, Any], ...]:
    """Load and prepare all upazila polygons once per process."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    upazilas: list[dict[str, Any]] = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        gtype = geometry.get("type")
        coords = geometry.get("coordinates", [])
        polygons = coords if gtype == "MultiPolygon" else [coords]
        min_lat, max_lat, min_lon, max_lon = _extract_bbox(coords)
        upazilas.append(
            {
                "code": str(props.get("geocode") or props.get("id") or ""),
                "name": props.get("upazila") or "Unknown",
                "district": props.get("district") or "",
                "division": props.get("division") or "",
                "bbox": (min_lat, max_lat, min_lon, max_lon),
                "polygons": polygons,
            }
        )
    return tuple(upazilas)


class UpazilaRouter:
    """Point -> upazila lookup using the local BARC boundary file."""

    def __init__(self, polygons_path: str | Path | None = None) -> None:
        self.path = Path(polygons_path or POLYGONS_FILE)
        self.upazilas = _load_upazilas(str(self.path))

    def route(self, latitude: float, longitude: float) -> RouteDecision:
        """Resolve one coordinate. Called only after S4 has a location."""
        if not (
            BD_MIN_LAT <= latitude <= BD_MAX_LAT
            and BD_MIN_LON <= longitude <= BD_MAX_LON
        ):
            return RouteDecision(
                is_bangladesh=False,
                upazila_code=None,
                upazila_name=None,
                district_name=None,
                division_name=None,
                method="national_envelope_rejection",
                candidates_count=0,
            )

        candidates = [
            item
            for item in self.upazilas
            if item["bbox"][0] <= latitude <= item["bbox"][1]
            and item["bbox"][2] <= longitude <= item["bbox"][3]
        ]
        if not candidates:
            return RouteDecision(
                is_bangladesh=False,
                upazila_code=None,
                upazila_name=None,
                district_name=None,
                division_name=None,
                method="aabb_empty_rejection",
                candidates_count=0,
            )

        for item in candidates:
            if any(
                point_in_polygon(latitude, longitude, polygon)
                for polygon in item["polygons"]
            ):
                return self._decision(item, "narrow_phase_pip", len(candidates))

        # Just outside a clipped border polygon: pick the nearest candidate centre.
        best = min(
            candidates,
            key=lambda item: self._centre_distance(item, latitude, longitude),
        )
        return self._decision(best, "border_nearest_aabb_fallback", len(candidates))

    @staticmethod
    def _centre_distance(item: dict[str, Any], lat: float, lon: float) -> float:
        min_lat, max_lat, min_lon, max_lon = item["bbox"]
        return (lat - (min_lat + max_lat) / 2.0) ** 2 + (
            lon - (min_lon + max_lon) / 2.0
        ) ** 2

    @staticmethod
    def _decision(
        item: dict[str, Any], method: str, candidates_count: int
    ) -> RouteDecision:
        return RouteDecision(
            is_bangladesh=True,
            upazila_code=item["code"],
            upazila_name=item["name"],
            district_name=item["district"],
            division_name=item["division"],
            method=method,
            candidates_count=candidates_count,
        )
