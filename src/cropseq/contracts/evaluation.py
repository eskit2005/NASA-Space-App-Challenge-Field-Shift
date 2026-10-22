"""S6 output: sequences with scores."""

from pydantic import BaseModel

from .common import StageOutput


class EvaluatedSequence(BaseModel):
    sequence_id: str
    crop_ids: list[str]
    # One number per objective. Keys come from `objectives` in config.py.
    # e.g. {"gross_margin": 1200.0, "water_m3": 800.0}
    # Pipeline checks these keys match config (Pydantic can't).
    metrics: dict[str, float]
    is_pareto_optimal: bool = False
    notes: dict[str, str] = {}  # free extras, e.g. {"label": "max profit"}


class EvaluatedSequences(StageOutput):
    """Produced by: S6. Consumed by: S7, S8."""

    sequences: list[EvaluatedSequence] = []
