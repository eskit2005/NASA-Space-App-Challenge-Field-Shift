"""S3 soil normalization: raw SoilGrids JSON -> clean `SoilProfile`.

1. Index the payload's `properties.layers` by property name.
2. Read each depth's raw `values.mean` and convert it with `d_factor`
   (clay, sand, silt, soc, phh2o, cec /10; bdod /100; nitrogen /100).
3. Average depths by their thickness (a 30 cm layer counts more than 5 cm).
4. Use 0-30 cm for the soil profile and 15-100 cm for the drainage indicator.
5. Farmer `soil_overrides` win over the grid value and set `is_field_tested`.
6. Nulls, missing layers and -999 fill values are skipped, never guessed.
"""

from __future__ import annotations

from typing import Any

from cropseq.contracts import SoilProfile

# Fallbacks if a layer does not carry `unit_measure.d_factor`.
D_FACTORS = {
    "clay": 10.0,
    "sand": 10.0,
    "silt": 10.0,
    "soc": 10.0,
    "phh2o": 10.0,
    "nitrogen": 100.0,
    "cec": 10.0,
    "bdod": 100.0,
    "cfvo": 10.0,
}
TOP_DEPTH_CM = 0.0
SOIL_BOTTOM_CM = 30.0
DRAINAGE_TOP_CM = 15.0
DRAINAGE_BOTTOM_CM = 100.0


def _layers(soil_raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map soil property name -> raw layer object."""
    layers = soil_raw.get("properties", {}).get("layers", [])
    return {
        layer["name"]: layer
        for layer in layers
        if isinstance(layer, dict) and layer.get("name")
    }


def _depth_span(depth: dict[str, Any]) -> tuple[float, float] | None:
    """Return (top, bottom) in cm from a depth record, or None if unreadable."""
    span = depth.get("range") or {}
    top = span.get("top_depth")
    bottom = span.get("bottom_depth")
    if isinstance(top, (int, float)) and isinstance(bottom, (int, float)):
        return float(top), float(bottom)

    label = str(depth.get("label", "")).replace("cm", "")
    if "-" in label:
        left, right = label.split("-", 1)
        try:
            return float(left), float(right)
        except ValueError:
            return None
    return None


def depth_mean(
    soil_raw: dict[str, Any],
    property_name: str,
    *,
    top_cm: float = TOP_DEPTH_CM,
    bottom_cm: float = SOIL_BOTTOM_CM,
) -> float | None:
    """Thickness-weighted mean of one property between two depths.

    Only depths that overlap the requested window count. Returns None when the
    property is missing or every value is null/fill.
    """
    layer = _layers(soil_raw).get(property_name)
    if not layer:
        return None

    d_factor = layer.get("unit_measure", {}).get("d_factor")
    try:
        d_factor = float(d_factor)
    except TypeError, ValueError:
        d_factor = D_FACTORS.get(property_name, 1.0)
    if d_factor == 0:
        d_factor = 1.0

    weighted_sum = 0.0
    total_weight = 0.0
    for depth in layer.get("depths", []):
        if not isinstance(depth, dict):
            continue
        span = _depth_span(depth)
        if span is None:
            continue
        depth_top, depth_bottom = span
        overlap = min(bottom_cm, depth_bottom) - max(top_cm, depth_top)
        if overlap <= 0:
            continue

        value = (depth.get("values") or {}).get("mean")
        if not isinstance(value, (int, float)) or value <= -999:
            continue

        weighted_sum += (float(value) / d_factor) * overlap
        total_weight += overlap

    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def topsoil_sand_pct(soil_raw: dict[str, Any]) -> float | None:
    """Sand percentage in the top 30 cm (used to discount clay drainage)."""
    return depth_mean(
        soil_raw,
        "sand",
        top_cm=TOP_DEPTH_CM,
        bottom_cm=SOIL_BOTTOM_CM,
    )


def drainage_clay_pct(soil_raw: dict[str, Any]) -> float | None:
    """Average clay percentage between 15 and 100 cm."""
    return depth_mean(
        soil_raw,
        "clay",
        top_cm=DRAINAGE_TOP_CM,
        bottom_cm=DRAINAGE_BOTTOM_CM,
    )


def build_soil_profile(
    soil_raw: dict[str, Any],
    overrides: dict[str, float],
) -> tuple[SoilProfile, list[str]]:
    """Convert the raw payload into a `SoilProfile` plus warnings."""
    warnings: list[str] = []

    grid_ph = depth_mean(soil_raw, "phh2o")
    ph = float(overrides["ph"]) if "ph" in overrides else grid_ph
    if "ph" in overrides:
        warnings.append(
            "ph taken from farmer soil_overrides (field-tested), grid estimate ignored"
        )
    elif grid_ph is None:
        warnings.append("SoilGrids returned no pH; ph left empty")

    organic_carbon = depth_mean(soil_raw, "soc")
    clay = depth_mean(soil_raw, "clay")
    sand = depth_mean(soil_raw, "sand")
    silt = depth_mean(soil_raw, "silt")
    nitrogen = depth_mean(soil_raw, "nitrogen")
    cec = depth_mean(soil_raw, "cec")
    bulk_density = depth_mean(soil_raw, "bdod")

    attributes: dict[str, float] = {}
    extras = {
        "clay_pct": clay,
        "sand_pct": sand,
        "silt_pct": silt,
        "total_nitrogen_g_kg": nitrogen,
        "cec_cmol_per_kg": cec,
        "bulk_density_kg_dm3": bulk_density,
    }
    for key, value in extras.items():
        if value is not None:
            attributes[key] = round(value, 3)

    if not _layers(soil_raw):
        warnings.append("No soil data available; soil profile is empty")

    return (
        SoilProfile(
            ph=round(ph, 3) if ph is not None else None,
            organic_carbon_g_kg=(
                round(organic_carbon, 3) if organic_carbon is not None else None
            ),
            texture=None,
            is_field_tested="ph" in overrides,
            attributes=attributes,
        ),
        warnings,
    )
