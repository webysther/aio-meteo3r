"""Constants of aiometeo3r."""

from __future__ import annotations

from typing import Final
from zoneinfo import ZoneInfo

ROME_TZ: Final = ZoneInfo("Europe/Rome")
"""Time zone of the times Meteo 3R publishes (``DATA_ORA``): Italian time."""

PIEMONTE_NETWORK: Final = "PIE"
"""Network of the Piedmont stations (``IDRETE``).

Meteo 3R also lists the stations of Liguria (LIG) and Valle d'Aosta (VDA),
which belong to other bodies, under other terms: aiometeo3r leaves them out.
"""

ATTRIBUTION: Final = "Fonte: Arpa Piemonte - www.arpa.piemonte.it"
"""Credit the data needs (CC BY 4.0, https://www.arpa.piemonte.it/note-legali)."""

DEFAULT_REQUEST_TIMEOUT: Final = 10.0
"""Seconds to wait for each answer of a host, before asking the next one.

Measured on 2026-11-17: the files answered in 0.11 s at the median and 0.21 s
at most (378 requests to both hosts); the list of stations is 280 KB.
"""

HOST_RETRY_AFTER: Final = 1800.0
"""Seconds a host that failed is asked last, after the other hosts.

Meteo 3R writes its files again every 30 minutes: a host that failed is asked
first again once it may have new files.
"""

REPOSITORY_URL: Final = "https://github.com/webysther/aio-meteo3r"
"""Home of aiometeo3r, named in its User-Agent."""
