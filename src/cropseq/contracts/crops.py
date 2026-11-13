"""Crop shape used by S4 and S5.

1. `Crop` keeps only three fixed fields; agronomic detail lives in `attributes`.
2. `attributes` may hold numbers, text, a list of season indexes, or a boolean
   (for example `is_legume`).
3. `FeasibleCrops` is S4's output: one crop list per season, plus the routing and
   land-type context S5/S6 need.
4. `supported=False` means the location is outside Bangladesh; the season lists
   are then empty on purpose.
5. `cropping_intensity_k` is how many of the listed seasons can actually be
   farmed (1-3).
6. `flags` marks the special regions: haor, coastal saline, deep wetland.
7. `routing` carries the upazila/district match details.
"""

from pydantic import BaseModel, Field

from .common import StageOutput


class Crop(BaseModel):
    crop_id: str
    name: str
    family: str  # botanical family, used for rotation rules
    # Everything else (pH range, growth days, yield, price, cost, water need,
    # nitrogen effect, root depth ...) goes here until we agree to promote it.
    attributes: dict[str, float | str | bool | list[int]] = {}


class FeasibleCrops(StageOutput):
    """Produced by: S4. Consumed by: S5.  Crops that can grow, per season."""

    by_season: dict[str, list[Crop]] = {}  # key = Season.name
    supported: bool = True
    land_type: str = ""
    cropping_intensity_k: int = Field(default=1, ge=0, le=3)
    flags: dict[str, bool] = {}
    routing: dict[str, str | int | float | bool | None] = {}
