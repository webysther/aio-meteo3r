"""Async client for the measurements of the Meteo 3R app of Arpa Piemonte.

Meteo 3R is the weather app of Arpa Piemonte. Its files give, for each station
of the regional network, the readings of the last 3 days every 30 minutes:
river level, rain, temperature, humidity, wind and snow, with the alert
thresholds of the hydrometers. aiometeo3r reads the stations of Piedmont.

The data is by Arpa Piemonte, under CC BY 4.0: credit it with
:data:`ATTRIBUTION`. aiometeo3r is not affiliated with Arpa Piemonte.
"""

from .client import Meteo3rClient
from .const import (
    ATTRIBUTION,
    DEFAULT_REQUEST_TIMEOUT,
    HOST_RETRY_AFTER,
    PIEMONTE_NETWORK,
    ROME_TZ,
)
from .exceptions import (
    Meteo3rConnectionError,
    Meteo3rError,
    Meteo3rNotFoundError,
    Meteo3rParseError,
)
from .models import (
    DailyExtremes,
    LevelStatus,
    Quantity,
    Reading,
    SensorType,
    Series,
    Station,
    StationData,
    Thresholds,
)
from .urls import Host

__all__ = [
    "ATTRIBUTION",
    "DEFAULT_REQUEST_TIMEOUT",
    "HOST_RETRY_AFTER",
    "PIEMONTE_NETWORK",
    "ROME_TZ",
    "DailyExtremes",
    "Host",
    "LevelStatus",
    "Meteo3rClient",
    "Meteo3rConnectionError",
    "Meteo3rError",
    "Meteo3rNotFoundError",
    "Meteo3rParseError",
    "Quantity",
    "Reading",
    "SensorType",
    "Series",
    "Station",
    "StationData",
    "Thresholds",
    "__version__",
]

__version__ = "0.1.0"
