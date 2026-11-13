"""S2 adapters: the code that talks to the outside world.

1. `http.py` is the shared HTTP client (timeout + retries).
2. `soilgrids.py` fetches raw soil data from ISRIC SoilGrids.
3. `open_meteo.py` fetches raw weather data from Open-Meteo.
4. `nasa_power.py` fetches raw agro-climate data from NASA POWER.

Each adapter implements a port from `ports.py`.
"""

from .http import HttpClient
from .nasa_power import NasaPowerAdapter
from .open_meteo import OpenMeteoAdapter
from .soilgrids import SoilGridsAdapter

__all__ = [
    "HttpClient",
    "NasaPowerAdapter",
    "OpenMeteoAdapter",
    "SoilGridsAdapter",
]
