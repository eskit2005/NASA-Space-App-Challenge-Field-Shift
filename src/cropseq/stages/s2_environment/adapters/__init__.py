"""Adapters for S2 environment providers."""

from .fake import FakeSoilProvider, FakeWeatherProvider
from .http import HttpClient
from .open_meteo import OpenMeteoAdapter
from .soilgrids import SoilGridsAdapter

__all__ = [
    "FakeSoilProvider",
    "FakeWeatherProvider",
    "HttpClient",
    "OpenMeteoAdapter",
    "SoilGridsAdapter",
]
