"""S4 filtering: location -> verified land type -> crop pools per season.

1. Use the S3 `Environment` (location + land-type check); load s3_output.json
   when the stage runs standalone.
2. Route the coordinate to one of the 505 Bangladesh upazilas.
3. Outside Bangladesh: return a clear "not supported yet" result, not an error.
4. Read BARC CZIS crop suitability for that upazila (local database first, then
   the BARC API, then a same-district fallback).
5. Apply the farmer's land type (never the estimate) and the region rules.
6. Return `FeasibleCrops`: crop lists, K, flags, routing and warnings.
"""

from __future__ import annotations

from pathlib import Path

from cropseq.config import config
from cropseq.contracts import Environment, FeasibleCrops

from .adapters.barc import BarcCatalog
from .adapters.fake import FakeCropCatalog
from .ports import CropCatalog
from .router import UpazilaRouter
from .selection import canonical_land_type, select_candidate_pools

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
S3_OUTPUT = DATA / "s3_output.json"

NOT_SUPPORTED = (
    "This location is outside Bangladesh. The global crop path is not supported "
    "yet; only the Bangladesh BARC crop path is available."
)


def _catalog() -> CropCatalog:
    """Build the configured crop catalog adapter."""
    name = config.adapters.get("crops") or config.adapter_crops
    if name == "barc":
        return BarcCatalog(db_path=config.barc_db)
    if name == "fake":
        return FakeCropCatalog()
    raise NotImplementedError(
        f"Crops adapter '{name}' is not implemented. Create "
        f"'src/cropseq/stages/s4_filtering/adapters/{name}.py' and register "
        "it in _catalog() in src/cropseq/stages/s4_filtering/service.py."
    )


def _unsupported(environment: Environment, routing: dict[str, object]) -> FeasibleCrops:
    """A clear, stable answer for a coordinate we cannot serve yet."""
    return FeasibleCrops(
        by_season={season.name: [] for season in config.seasons},
        supported=False,
        land_type=canonical_land_type(environment.land_type_check.used_land_type),
        cropping_intensity_k=0,
        flags={},
        routing=routing,
        warnings=[NOT_SUPPORTED],
        source="S4 filtering (Bangladesh only)",
    )


def run(environment: Environment | None = None) -> FeasibleCrops:
    """Return the candidate crops for each season at the farm location.

    Standalone: loads s3_output.json. The pipeline passes S3's Environment.
    """
    if environment is None:
        environment = Environment.model_validate_json(
            S3_OUTPUT.read_text(encoding="utf-8")
        )

    router = UpazilaRouter(polygons_path=config.barc_polygons)
    route = router.route(
        latitude=environment.location.latitude,
        longitude=environment.location.longitude,
    )
    routing = route.to_dict()
    if not route.is_bangladesh or not route.upazila_code:
        return _unsupported(environment, routing)

    catalog = _catalog()
    result = catalog.get_records(route.upazila_code)
    selected = select_candidate_pools(
        records=result.records,
        land_type=environment.land_type_check.used_land_type,
        district_name=route.district_name,
        season_names=[season.name for season in config.seasons],
    )

    return FeasibleCrops(
        by_season=selected.by_season,
        supported=True,
        land_type=canonical_land_type(environment.land_type_check.used_land_type),
        cropping_intensity_k=selected.k,
        flags=selected.flags,
        routing=routing,
        warnings=[*result.warnings, *selected.warnings],
        source=f"S4 filtering | {result.source}",
    )
