"""Small building blocks shared by several contracts.

RULES FOR EVERY FILE IN contracts/
  - Only things that cross a stage boundary live here.
  - Units go in the field name (area_ha, water_m3, cost_usd_per_ha).
  - Need to carry extra data without changing the class? Use the
    `attributes` / `metrics` dict. Need a real new field? Add it here and
    tell the team (this folder is shared).
"""

from pydantic import BaseModel, Field


class Season(BaseModel):
    """One growing season. Seasons are DATA, never hard-coded in stages."""

    name: str  # e.g. "season_1" (edit names/months in config.py)
    start_month: int = Field(ge=1, le=12)
    end_month: int = Field(ge=1, le=12)  # may be < start_month if it wraps the year


class StageOutput(BaseModel):
    """Base class for every stage's output. Gives all outputs the same two extras."""

    # Problems that did NOT stop the pipeline but the user should know about.
    # e.g. "SoilGrids returned null, default pH used"
    warnings: list[str] = []
    # Where the data came from, for the audit stage. e.g. "SoilGrids, 2026-10-05"
    source: str = ""


class EvidenceReference(BaseModel):
    """A source backing a claim. Produced by S7 (explanation), checked by S8 (audit)."""

    source_id: str
    title: str
    url: str | None = None
    claim: str = ""  # the statement this source supports
