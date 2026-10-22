"""Ports (Protocol interfaces) for S4. Adapters implement these."""

from typing import Protocol

from cropseq.contracts import Crop


class CropCatalog(Protocol):
    """Supplies the crop catalog (web API / file / in-memory)."""

    def get_crops(self) -> list[Crop]: ...
