"""Adapters for S3 normalization.

1. `fao.py` fetches raw crop-calendar records from the FAO API.
2. Each adapter implements a port from `ports.py`.
"""

from .fao import FaoCropCalendarAdapter

__all__ = ["FaoCropCalendarAdapter"]
