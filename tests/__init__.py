"""Tests of aiometeo3r."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from aiometeo3r import ROME_TZ, Host
from aiometeo3r.urls import REGISTRY_PATH, station_path

FIXTURES = Path(__file__).parent / "fixtures"
REAL = FIXTURES / "real"
"""Unmodified files of Meteo 3R, downloaded on 2026-11-17 at 02:28 UTC."""

PRAY = "188"
"""Pray Sessera, on the Sessera: a hydrometer with all three thresholds."""
COLLE_LOMBARDA = "001"
"""Colle Lombarda: wind, humidity and snow, with the daily snow depth."""
MALCIAUSSIA = "349"
"""Malciaussia: no readings at all (DATI is empty)."""

REGISTRY_URL = Host.PRIMARY.url(REGISTRY_PATH)
MIRROR_REGISTRY_URL = Host.MIRROR.url(REGISTRY_PATH)


def station_url(code: str, host: Host = Host.PRIMARY) -> str:
    """Return the URL of a station file on a host."""
    return host.url(station_path(code))


def real_bytes(name: str) -> bytes:
    """Return a real file of Meteo 3R, byte for byte."""
    return (REAL / name).read_bytes()


def real_json(name: str) -> object:
    """Return the decoded JSON of a real file of Meteo 3R."""
    data: object = json.loads(real_bytes(name))
    return data


def station_file(code: str) -> object:
    """Return the decoded real file of a station."""
    return real_json(f"misure_PIE_{code}.json")


def utc(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> dt.datetime:
    """Return an aware datetime in UTC."""
    return dt.datetime(year, month, day, hour, minute, tzinfo=dt.UTC)


def rome(
    year: int, month: int, day: int, hour: int = 0, minute: int = 0
) -> dt.datetime:
    """Return an aware datetime in Europe/Rome."""
    return dt.datetime(year, month, day, hour, minute, tzinfo=ROME_TZ)
