"""Addresses of the Meteo 3R files.

The app lists them in https://www.meteo3r.it/assets/data/urls_staticm3r.json
and urls_aruba.json: the same files on two hosts.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final

from .const import PIEMONTE_NETWORK


class Host(StrEnum):
    """A host of the Meteo 3R files, by its base URL."""

    PRIMARY = "https://staticm3r.arpa.piemonte.it/meteo3r_production/"
    """The server of Arpa Piemonte (urls_staticm3r.json)."""
    MIRROR = "https://www.meteo3r.it/dati/"
    """The hosting of the app (urls_aruba.json)."""

    def url(self, path: str) -> str:
        """Return the URL of a file on this host."""
        return f"{self.value}{path}"


REGISTRY_PATH: Final = "misure/misureAnagrafica.json"
"""The list of the stations, of every network (``MISURE_ANAGRAFICA``)."""

_STATION_CODE: Final = re.compile(r"[0-9A-Za-z]+")
"""A station code: letters and digits, as in ``CODSTAZ``."""


def station_path(code: str) -> str:
    """Return the path of the measurements of a Piedmont station.

    Raises ``ValueError`` for a code that is not letters and digits.
    """
    if not _STATION_CODE.fullmatch(code):
        msg = f"Invalid station code: {code!r}"
        raise ValueError(msg)
    return f"misure/misure_{PIEMONTE_NETWORK}_{code}.json"
