"""Working fake adapter for S4: crops come from the stage fixture."""

from cropseq.contracts import Crop

from ..fixture import load_fixture


class FakeCropCatalog:
    """Returns the placeholder crops stored in s4_output.json (deduplicated)."""

    def get_crops(self) -> list[Crop]:
        # TODO: replace with a real catalog call.
        seen: dict[str, Crop] = {}
        for crops in load_fixture()["by_season"].values():
            for raw in crops:
                crop = Crop.model_validate(raw)
                seen.setdefault(crop.crop_id, crop)
        return list(seen.values())
