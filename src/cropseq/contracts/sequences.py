"""S5 output: crop sequences that pass the rotation rules."""

from pydantic import BaseModel

from .common import StageOutput


class CandidateSequence(BaseModel):
    sequence_id: str
    crop_ids: list[str]  # one per season, in season order. Length = horizon (config.py)


class SequencePool(StageOutput):
    """Produced by: S5. Consumed by: S6."""

    sequences: list[CandidateSequence] = []
