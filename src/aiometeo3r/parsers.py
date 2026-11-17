"""Parsing of the Meteo 3R files, without I/O.

The files have no documented format. What is checked here was measured on the
374 stations of Piedmont on 2026-11-17:

- the station list (``misureAnagrafica.json``) is a list of stations of every
  network; aiometeo3r keeps those of Piedmont;
- a station file holds the station (``ANAGRAFICA``), parallel lists of readings
  every 30 minutes over about 3 days (``DATI``), and the latest values with the
  extremes of today (``DATI_STAT``);
- a series the station does not measure is a list of nulls; two stations had
  no readings at all (``DATI`` empty);
- the times are Italian times without offset ("2026-11-17 03:00").
"""

from __future__ import annotations

import datetime as dt
import logging
import math
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Final

from .const import PIEMONTE_NETWORK, ROME_TZ
from .exceptions import Meteo3rParseError
from .models import (
    DailyExtremes,
    Quantity,
    Reading,
    SensorType,
    Series,
    Station,
    StationData,
    Thresholds,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_LOGGER = logging.getLogger(__name__)

TIME_FORMAT: Final = "%Y-%m-%d %H:%M"
"""Format of the times of Meteo 3R, in Italian time."""

TIMES_KEY: Final = "DATA_ORA"
"""Times of the readings in ``DATI``."""

DAILY_TIMES_KEY: Final = "DATA_ORA_HS_V"
"""Times of the daily snow depth in ``DATI``: it has its own."""

IGNORED_KEYS: Final = frozenset({"I_STATO"})
"""Series of ``DATI`` that aiometeo3r reads as known but does not return.

``I_STATO`` was 0 with every level and 4 only where the level is missing
(measured on 2026-11-17, 16,677 readings): it says nothing the level does not.
"""

EXTREME_QUANTITIES: Final = (
    Quantity.LEVEL,
    Quantity.TEMPERATURE,
    Quantity.HUMIDITY,
    Quantity.GUST_SPEED,
    Quantity.SNOW_DEPTH,
)
"""Quantities whose extremes of today ``DATI_STAT`` gives (``*_MAX``, ``*_MIN``)."""

_EMPTY_TEXTS: Final = frozenset({"", "-"})
"""Texts Meteo 3R writes for a missing value ("-" for the river of a rain gauge)."""


def parse_registry(data: object) -> tuple[Station, ...]:
    """Return the stations of Piedmont of the station list.

    A station that cannot be read is left out (logged at debug level). Raises
    :class:`Meteo3rParseError` when the list is not a list or has no station
    of Piedmont.
    """
    if not isinstance(data, list):
        msg = "The station list is not a list"
        raise Meteo3rParseError(msg)
    stations: list[Station] = []
    for record in data:
        if not isinstance(record, Mapping) or record.get("IDRETE") != PIEMONTE_NETWORK:
            continue
        try:
            stations.append(parse_station(record))
        except Meteo3rParseError as err:
            _LOGGER.debug("Station left out: %s", err)
    if not stations:
        msg = "The station list has no station of Piedmont"
        raise Meteo3rParseError(msg)
    return tuple(stations)


def parse_station(record: Mapping[str, object]) -> Station:
    """Return a station from its record (``ANAGRAFICA``).

    Raises :class:`Meteo3rParseError` without code, name or coordinates.
    """
    code = _required_text(record, "CODSTAZ")
    letters = _text(record, "TIPO") or ""
    return Station(
        code=code,
        name=_required_text(record, "DENOMINAZIONE"),
        latitude=_required_number(record, "LAT"),
        longitude=_required_number(record, "LON"),
        altitude=_optional_number(record, "QUOTA"),
        sensor_letters=letters,
        sensor_types=frozenset(SensorType.of(letter) for letter in letters),
        municipality=_text(record, "COMUNE") or "",
        municipality_code=_text(record, "ISTAT") or "",
        province=_text(record, "PROVINCIA") or "",
        province_code=_text(record, "SIGLA_PROVINCIA") or "",
        river=_text(record, "CORSO_ACQUA"),
        basin=_text(record, "BACINO_PLUV"),
        hydrometric_zero=parse_decimal(record.get("ZERO_IDROMETRICO")),
        thresholds=Thresholds(
            pre_alarm=parse_decimal(record.get("SOGLIA_PRE")),
            guard=parse_decimal(record.get("SOGLIA_GUARDIA")),
            danger=parse_decimal(record.get("SOGLIA_PERICOLO")),
        ),
        note=_text(record, "NOTE_STAZ"),
    )


def parse_station_file(data: object, code: str | None = None) -> StationData:
    """Return the station and the readings of a station file.

    With ``code``, the file must be that station's. Raises
    :class:`Meteo3rParseError` when the file does not have the expected format.
    """
    if not isinstance(data, Mapping):
        msg = "The station file is not an object"
        raise Meteo3rParseError(msg)
    record = data.get("ANAGRAFICA")
    if not isinstance(record, Mapping):
        msg = "The station file has no ANAGRAFICA"
        raise Meteo3rParseError(msg)
    station = parse_station(record)
    if code is not None and station.code != code:
        msg = f"Asked for station {code}, the file is of station {station.code}"
        raise Meteo3rParseError(msg)
    readings = data.get("DATI")
    if readings is None:
        readings = {}
    if not isinstance(readings, Mapping):
        msg = f"DATI of station {station.code} is not an object"
        raise Meteo3rParseError(msg)

    texts = _times(readings, TIMES_KEY)
    times = rome_times_to_utc(texts)
    series = [
        _series(quantity, times, readings)
        for quantity in Quantity
        if quantity is not Quantity.DAILY_SNOW_DEPTH
    ]
    daily_times = rome_times_to_utc(_times(readings, DAILY_TIMES_KEY))
    series.append(_series(Quantity.DAILY_SNOW_DEPTH, daily_times, readings))
    known = {TIMES_KEY, DAILY_TIMES_KEY, *IGNORED_KEYS, *Quantity}
    statistics = data.get("DATI_STAT")
    if statistics is None:
        statistics = {}
    if not isinstance(statistics, Mapping):
        msg = f"DATI_STAT of station {station.code} is not an object"
        raise Meteo3rParseError(msg)
    found = tuple(item for item in series if item)
    return StationData(
        station=station,
        series=found,
        extremes=_extremes(statistics, _time_resolver(texts, times, found)),
        other_keys=tuple(sorted(str(key) for key in readings if key not in known)),
    )


def rome_times_to_utc(texts: Sequence[str]) -> list[dt.datetime | None]:
    """Return the instants of chronological Italian times, in UTC.

    Each time becomes its first instant after the previous one, which places
    the hour that repeats when summer time ends: "02:30" is first 00:30 UTC,
    then 01:30 UTC. A time that does not exist (when summer time starts) or
    that does not come after the previous one becomes None.

    Raises :class:`Meteo3rParseError` for a text that is not a time.
    """
    instants: list[dt.datetime | None] = []
    previous: dt.datetime | None = None
    for text in texts:
        instant = next(
            (
                candidate
                for candidate in _instants(_wall_clock(text))
                if previous is None or candidate > previous
            ),
            None,
        )
        instants.append(instant)
        if instant is not None:
            previous = instant
    return instants


def parse_decimal(value: object) -> float | None:
    """Return a number written as text by Meteo 3R ("2.3", "3", "").

    The thresholds and the hydrometric zero are texts, empty when missing. A
    number is returned as a float. None for an empty or unreadable value.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        number = float(value)
    elif isinstance(value, str) and value.strip() not in _EMPTY_TEXTS:
        try:
            number = float(value.strip().replace(",", "."))
        except ValueError:
            _LOGGER.debug("Not a number: %r", value)
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _wall_clock(text: str) -> dt.datetime:
    """Return an Italian time without time zone, from its text."""
    try:
        return dt.datetime.strptime(text, TIME_FORMAT)  # noqa: DTZ007 - Italian time, placed by _instants
    except ValueError as err:
        msg = f"Not a time: {text!r}"
        raise Meteo3rParseError(msg) from err


def _instants(wall: dt.datetime) -> list[dt.datetime]:
    """Return the instants of an Italian time, in UTC, from the earliest.

    One for most times, two for the hour that repeats when summer time ends,
    none for the hour skipped when it starts.
    """
    instants = set()
    for fold in (0, 1):
        instant = wall.replace(tzinfo=ROME_TZ, fold=fold).astimezone(dt.UTC)
        if instant.astimezone(ROME_TZ).replace(tzinfo=None) == wall:
            instants.add(instant)
    return sorted(instants)


def _times(readings: Mapping[str, object], key: str) -> list[str]:
    """Return the texts of the times of the readings; empty without readings."""
    texts = readings.get(key)
    if texts is None:
        return []
    if not isinstance(texts, list):
        msg = f"{key} is not a list"
        raise Meteo3rParseError(msg)
    return [_text_of(text) for text in texts]


def _text_of(text: object) -> str:
    if not isinstance(text, str):
        msg = f"Not a time: {text!r}"
        raise Meteo3rParseError(msg)
    return text


def _series(
    quantity: Quantity,
    times: Sequence[dt.datetime | None],
    readings: Mapping[str, object],
) -> Series:
    """Return the series of a quantity: the times that have a value."""
    values = readings.get(quantity.value)
    if values is None:
        return Series(quantity)
    if not isinstance(values, list) or len(values) != len(times):
        msg = f"{quantity.value} is not a list as long as its times"
        raise Meteo3rParseError(msg)
    return Series(
        quantity,
        tuple(
            Reading(time, number)
            for time, value in zip(times, values, strict=True)
            if time is not None and (number := _reading(quantity, value)) is not None
        ),
    )


def _reading(quantity: Quantity, value: object) -> float | None:
    """Return the value of a reading; None when it is missing."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        msg = f"{quantity.value} has a value that is not a number: {value!r}"
        raise Meteo3rParseError(msg)
    number = float(value)
    return number if math.isfinite(number) else None


def _time_resolver(
    texts: Sequence[str],
    times: Sequence[dt.datetime | None],
    series: Sequence[Series],
) -> Callable[[str, Quantity, float], dt.datetime]:
    """Return how to place a time of ``DATI_STAT``, by the readings of ``DATI``.

    A time of the readings is placed as there. When it repeats (the hour when
    summer time ends), the one where the quantity has the same value wins,
    else the latest. A time not among the readings is taken as the first.
    """
    instants: dict[str, list[dt.datetime]] = {}
    for text, time in zip(texts, times, strict=True):
        if time is not None:
            instants.setdefault(text, []).append(time)
    by_quantity = {item.quantity: item for item in series}

    def resolve(text: str, quantity: Quantity, value: float) -> dt.datetime:
        candidates = instants.get(text)
        if not candidates:
            return _instants_or_first(text)
        readings = by_quantity.get(quantity)
        return next(
            (
                time
                for time in reversed(candidates)
                if readings is not None
                and (reading := readings.at(time)) is not None
                and reading.value == value
            ),
            candidates[-1],
        )

    return resolve


def _instants_or_first(text: str) -> dt.datetime:
    wall = _wall_clock(text)
    instants = _instants(wall)
    if instants:
        return instants[0]
    return wall.replace(tzinfo=ROME_TZ).astimezone(dt.UTC)


def _extremes(
    statistics: Mapping[str, object],
    resolve: Callable[[str, Quantity, float], dt.datetime],
) -> tuple[DailyExtremes, ...]:
    """Return the extremes of today of ``DATI_STAT``, for the quantities with them."""
    extremes = []
    for quantity in EXTREME_QUANTITIES:
        maximum = _statistic(statistics, f"{quantity.value}_MAX", quantity, resolve)
        minimum = _statistic(statistics, f"{quantity.value}_MIN", quantity, resolve)
        if maximum is not None or minimum is not None:
            extremes.append(DailyExtremes(quantity, maximum, minimum))
    return tuple(extremes)


def _statistic(
    statistics: Mapping[str, object],
    key: str,
    quantity: Quantity,
    resolve: Callable[[str, Quantity, float], dt.datetime],
) -> Reading | None:
    value = parse_decimal(statistics.get(key))
    text = statistics.get(f"{key}_DATA")
    if value is None or not isinstance(text, str):
        return None
    return Reading(resolve(text, quantity, value), value)


def _text(record: Mapping[str, object], key: str) -> str | None:
    """Return a text of a record, stripped; None when missing or empty."""
    value = record.get(key)
    if not isinstance(value, str) or value.strip() in _EMPTY_TEXTS:
        return None
    return value.strip()


def _required_text(record: Mapping[str, object], key: str) -> str:
    value = _text(record, key)
    if value is None:
        msg = f"Station without {key}: {record.get('IDRETE_CODSTAZ')!r}"
        raise Meteo3rParseError(msg)
    return value


def _optional_number(record: Mapping[str, object], key: str) -> float | None:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def _required_number(record: Mapping[str, object], key: str) -> float:
    value = _optional_number(record, key)
    if value is None:
        msg = f"Station without {key}: {record.get('IDRETE_CODSTAZ')!r}"
        raise Meteo3rParseError(msg)
    return value
