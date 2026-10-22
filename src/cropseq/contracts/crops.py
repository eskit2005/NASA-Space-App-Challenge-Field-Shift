"""Crop shape. NOT final: the stage owner decides what goes in `attributes`.
Only the three fields every stage needs are fixed."""

from pydantic import BaseModel

from .common import StageOutput


class Crop(BaseModel):
    crop_id: str
    name: str
    family: str  # botanical family, used for rotation rules
    # Everything else (pH range, growth days, yield, price, cost, water need,
    # nitrogen effect, root depth ...) goes here until we agree to promote it.
    attributes: dict[str, float | str | list[int]] = {}


class FeasibleCrops(StageOutput):
    """Produced by: S4. Consumed by: S5.  Crops that can grow, per season."""

    by_season: dict[str, list[Crop]] = {}  # key = Season.name
