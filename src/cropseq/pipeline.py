"""The only module that wires the stages together, in order.

run(profile) -> FinalResponse
"""

from .config import config
from .contracts import EvaluatedSequences, FarmerProfile, FinalResponse
from .errors import CropseqError
from .stages.s1_intake import service as s1
from .stages.s2_environment import service as s2
from .stages.s3_normalization import service as s3
from .stages.s4_filtering import service as s4
from .stages.s5_sequences import service as s5
from .stages.s6_optimization import service as s6
from .stages.s7_explanation import service as s7
from .stages.s8_audit import service as s8


def _check_metric_keys(evaluated: EvaluatedSequences) -> None:
    """S6 must score exactly the objectives declared in config.py."""
    expected = set(config.objectives)
    for seq in evaluated.sequences:
        actual = set(seq.metrics)
        if actual != expected:
            raise CropseqError(
                f"S6 metric keys {sorted(actual)} do not match "
                f"config.objectives {sorted(expected)} for {seq.sequence_id}"
            )


def run(profile: FarmerProfile) -> FinalResponse:
    """Execute S1..S8 in order and return the audited recommendation."""
    farmer = s1.run(profile)
    raw = s2.run(farmer.location)
    environment = s3.run(profile=farmer, raw=raw)
    feasible = s4.run(environment)
    pool = s5.run(feasible)
    evaluated = s6.run(pool=pool, environment=environment, profile=farmer)
    _check_metric_keys(evaluated)
    explanation = s7.run(evaluated)
    return s8.run(explanation=explanation, evaluated=evaluated)
