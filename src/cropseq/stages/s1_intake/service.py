"""S1 intake: validate the request and apply defaults.

1. Accept the `FarmerProfile` the API or CLI already parsed.
2. For standalone runs, load data/data_shape/s1_input.json.
3. Re-validate through the contract, so a direct Python caller gets the same checks.
4. If `priorities` is empty, give every objective in config.py equal weight.
5. Return the farmer's own values. Nothing is replaced with fixture data.

This stage is the pipeline's source of truth: everything after it uses this profile.
"""

from pathlib import Path

from cropseq.config import config
from cropseq.contracts import FarmerProfile

DATA = Path(__file__).resolve().parents[4] / "data" / "data_shape"
INPUT = DATA / "s1_input.json"


def run(profile: FarmerProfile | None = None) -> FarmerProfile:
    """Validate the incoming profile and fill default priorities.

    Standalone: loads data/data_shape/s1_input.json.
    """
    if profile is None:
        profile = FarmerProfile.model_validate_json(INPUT.read_text(encoding="utf-8"))

    data = profile.model_dump()
    if not data.get("priorities"):
        weight = 1.0 / len(config.objectives)
        data["priorities"] = {objective: weight for objective in config.objectives}

    return FarmerProfile.model_validate(data)
