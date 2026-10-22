"""S4 filtering: environment -> feasible crops per season (adapter-driven)."""

from cropseq.config import config
from cropseq.contracts import Crop, Environment, FeasibleCrops

from .adapters.fake import FakeCropCatalog
from .fixture import load_fixture
from .ports import CropCatalog


def _catalog() -> CropCatalog:
    name = config.adapters["crops"]
    if name == "fake":
        return FakeCropCatalog()
    raise NotImplementedError(
        f"Crops adapter '{name}' is not implemented yet. Create "
        f"'src/cropseq/stages/s4_filtering/adapters/{name}.py' and register "
        "it in _catalog() in src/cropseq/stages/s4_filtering/service.py."
    )


def _suitable_seasons(crop: Crop) -> list[int]:
    value = crop.attributes.get("suitable_seasons")
    return value if isinstance(value, list) else []


def run(environment: Environment) -> FeasibleCrops:
    """Keep the crops that can grow in each configured season.

    Stub: feasibility = the catalog's `suitable_seasons` attribute.
    TODO: apply real rules (pH range, climate) from `environment`.
    """
    crops = _catalog().get_crops()
    by_season = {
        season.name: [c for c in crops if index in _suitable_seasons(c)]
        for index, season in enumerate(config.seasons, start=1)
    }
    data = load_fixture()
    return FeasibleCrops(
        by_season=by_season,
        warnings=data["warnings"],
        source=data["source"],
    )
