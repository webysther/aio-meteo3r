"""Models of the Meteo 3R stations and their measurements.

Every model is a frozen dataclass of plain values and tuples: two fetches of the
same data compare equal, whichever host served them.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import TYPE_CHECKING, Any, Final, Self

from .const import PIEMONTE_NETWORK

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class _NamedLevel(IntEnum):
    """Ordered level shown by its lower-case name: ``str(level) == "guard"``."""

    def __str__(self) -> str:
        return self.name.lower()

    def __format__(self, format_spec: str) -> str:
        return format(str(self), format_spec)

    @property
    def code(self) -> int:
        """Return the numeric code of the value: its number."""
        return int(self)

    @classmethod
    def from_code(cls, code: int) -> Self | None:
        """Return the value of a numeric code; None when no value has it."""
        return next((member for member in cls if member.code == code), None)


class _Coded(StrEnum):
    """A value named by the text Meteo 3R uses, with a numeric code."""

    @property
    def code(self) -> int:
        """Return the numeric code of the value."""
        return _CODES[type(self)][self]

    @classmethod
    def from_code(cls, code: int) -> Self | None:
        """Return the value of a numeric code; None when no value has it."""
        return next((member for member in cls if member.code == code), None)


class SensorType(_Coded):
    """A sensor of a station: one letter of its ``TIPO`` ("IPT").

    The letters come in any order. Their meaning is not documented: it is what
    the series of the 374 stations show (measured on 2026-11-17). G, W, S and F
    also appear, on stations whose series they do not change.
    """

    UNKNOWN = "?"
    """A letter aiometeo3r does not know: it is kept in ``sensor_letters``."""
    HYDROMETER = "I"
    """Water level of a river or lake (idrometro)."""
    RAIN_GAUGE = "P"
    """Rain (pluviometro)."""
    THERMOMETER = "T"
    """Air temperature (termometro)."""
    HYGROMETER = "H"
    """Relative humidity (igrometro)."""
    SNOW_GAUGE = "N"
    """Snow depth, hourly and daily (nivometro)."""
    ANEMOMETER = "V"
    """Wind and gust, speed and direction (anemometro)."""
    BAROMETER = "B"
    """Air pressure (barometro): Meteo 3R publishes no series of it."""
    RADIOMETER = "R"
    """Solar radiation (radiometro): Meteo 3R publishes no series of it."""

    @classmethod
    def of(cls, letter: str) -> SensorType:
        """Return the sensor of a letter of ``TIPO``; UNKNOWN when not known."""
        try:
            return cls(letter.upper())
        except ValueError:
            return cls.UNKNOWN


SENSOR_TYPE_CODES: Final[Mapping[SensorType, int]] = {
    SensorType.UNKNOWN: 0,
    SensorType.HYDROMETER: 1,
    SensorType.RAIN_GAUGE: 2,
    SensorType.THERMOMETER: 3,
    SensorType.HYGROMETER: 4,
    SensorType.SNOW_GAUGE: 5,
    SensorType.ANEMOMETER: 6,
    SensorType.BAROMETER: 7,
    SensorType.RADIOMETER: 8,
}
"""Codes of the sensor types, proposed by aiometeo3r."""


class Quantity(_Coded):
    """A measured quantity: a series of ``DATI``, named by its key."""

    LEVEL = "I"
    """Water level, in metres above the hydrometric zero."""
    TEMPERATURE = "T"
    """Air temperature, in °C."""
    HUMIDITY = "RH"
    """Relative humidity, in %."""
    RAIN_1H = "P_1H"
    """Rain in the hour that ends at the time of the reading, in mm."""
    RAIN_3H = "P_3H"
    """Rain in the 3 hours that end at the time of the reading, in mm."""
    RAIN_24H = "P_24H"
    """Rain in the 24 hours that end at the time of the reading, in mm."""
    WIND_SPEED = "VV"
    """Wind speed, in km/h."""
    WIND_DIRECTION = "DD"
    """Direction the wind comes from, in degrees."""
    GUST_SPEED = "VVR"
    """Speed of the strongest gust, in km/h."""
    GUST_DIRECTION = "DDR"
    """Direction the strongest gust comes from, in degrees."""
    SNOW_DEPTH = "HS"
    """Snow depth, in cm."""
    DAILY_SNOW_DEPTH = "HS_V"
    """Snow depth read once a day, at 08:00 Italian time, in cm.

    It has its own times (``DATA_ORA_HS_V``): the last 7 days, on the stations
    with a snow gauge (measured on 2026-11-17).
    """

    @property
    def unit(self) -> str:
        """Return the unit of the quantity."""
        return QUANTITY_UNITS[self]


QUANTITY_CODES: Final[Mapping[Quantity, int]] = {
    Quantity.LEVEL: 1,
    Quantity.TEMPERATURE: 3,
    Quantity.HUMIDITY: 4,
    Quantity.RAIN_1H: 5,
    Quantity.RAIN_3H: 6,
    Quantity.RAIN_24H: 7,
    Quantity.WIND_SPEED: 8,
    Quantity.WIND_DIRECTION: 9,
    Quantity.GUST_SPEED: 10,
    Quantity.GUST_DIRECTION: 11,
    Quantity.SNOW_DEPTH: 12,
    Quantity.DAILY_SNOW_DEPTH: 13,
}
"""Codes of the quantities, proposed by aiometeo3r."""

QUANTITY_UNITS: Final[Mapping[Quantity, str]] = {
    Quantity.LEVEL: "m",
    Quantity.TEMPERATURE: "°C",
    Quantity.HUMIDITY: "%",
    Quantity.RAIN_1H: "mm",
    Quantity.RAIN_3H: "mm",
    Quantity.RAIN_24H: "mm",
    Quantity.WIND_SPEED: "km/h",
    Quantity.WIND_DIRECTION: "°",
    Quantity.GUST_SPEED: "km/h",
    Quantity.GUST_DIRECTION: "°",
    Quantity.SNOW_DEPTH: "cm",
    Quantity.DAILY_SNOW_DEPTH: "cm",
}
"""Units of the quantities.

Meteo 3R publishes no units. Measured on 2026-11-17 against the official files
of Arpa Piemonte, which state theirs:

- every reading of the 374 stations equals the api_realtime of Arpa Piemonte
  at the same time (5,000 to 20,000 readings per quantity);
- level, temperature, humidity and snow equal the files of the Arpa website
  (m, °C, %, cm);
- the wind and the gust are 3.6 times the files of the Arpa website, in m/s
  (3.5 to 3.67, from the rounding): Meteo 3R gives them in km/h.
"""

_CODES: Final[Mapping[type[_Coded], Mapping[Any, int]]] = {
    SensorType: SENSOR_TYPE_CODES,
    Quantity: QUANTITY_CODES,
}
"""The table of codes of each enum named by a text."""


class LevelStatus(_NamedLevel):
    """The water level against the thresholds of the station, ordered.

    Levels compare with each other (``status >= LevelStatus.GUARD``).
    """

    UNKNOWN = 0
    """The station has no thresholds."""
    NORMAL = 1
    """Below every threshold."""
    PRE_ALARM = 2
    """At or above the pre-alarm threshold (soglia di preallarme)."""
    GUARD = 3
    """At or above the guard threshold (soglia di guardia)."""
    DANGER = 4
    """At or above the danger threshold (soglia di pericolo)."""


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Alert thresholds of a hydrometer, in metres above the hydrometric zero.

    Any of them can be missing: 26 of the 110 hydrometers of Piedmont lack at
    least one (measured on 2026-11-17).
    """

    pre_alarm: float | None = None
    """Pre-alarm threshold (``SOGLIA_PRE``)."""
    guard: float | None = None
    """Guard threshold (``SOGLIA_GUARDIA``)."""
    danger: float | None = None
    """Danger threshold (``SOGLIA_PERICOLO``)."""

    def status(self, level: float) -> LevelStatus:
        """Return the highest threshold the level reaches.

        A missing threshold is skipped; without any, the status is UNKNOWN.
        """
        limits = (
            (LevelStatus.DANGER, self.danger),
            (LevelStatus.GUARD, self.guard),
            (LevelStatus.PRE_ALARM, self.pre_alarm),
        )
        known = [(status, limit) for status, limit in limits if limit is not None]
        if not known:
            return LevelStatus.UNKNOWN
        return next(
            (status for status, limit in known if level >= limit), LevelStatus.NORMAL
        )


@dataclass(frozen=True, slots=True)
class Station:
    """A measuring station of the Piedmont network, as Meteo 3R lists it."""

    code: str
    """Code of the station in the network (``CODSTAZ``), leading zeros kept."""
    name: str
    """Name of the station (``DENOMINAZIONE``)."""
    latitude: float
    """Latitude, WGS84."""
    longitude: float
    """Longitude, WGS84."""
    altitude: float | None
    """Altitude of the station, in metres (``QUOTA``)."""
    sensor_letters: str
    """``TIPO`` as published, one letter per sensor in any order ("IPT")."""
    sensor_types: frozenset[SensorType]
    """The sensors of the station, from ``sensor_letters``."""
    municipality: str
    """Municipality of the station (``COMUNE``)."""
    municipality_code: str
    """ISTAT code of the municipality (``ISTAT``), the current one."""
    province: str
    """Province of the station (``PROVINCIA``)."""
    province_code: str
    """Abbreviation of the province (``SIGLA_PROVINCIA``), e.g. "BI"."""
    river: str | None
    """River or lake a hydrometer measures (``CORSO_ACQUA``)."""
    basin: str | None
    """Basin of the station (``BACINO_PLUV``)."""
    hydrometric_zero: float | None
    """Altitude of the zero of the level, in metres (``ZERO_IDROMETRICO``)."""
    thresholds: Thresholds
    """Alert thresholds of the level; all None for a station without hydrometer."""
    note: str | None = None
    """Note on the station (``NOTE_STAZ``)."""

    @property
    def id(self) -> str:
        """Return the identifier Meteo 3R uses: network and code, "PIE_188"."""
        return f"{PIEMONTE_NETWORK}_{self.code}"

    def has(self, sensor_type: SensorType) -> bool:
        """Return whether the station has a sensor."""
        return sensor_type in self.sensor_types


@dataclass(frozen=True, slots=True)
class Reading:
    """A value measured at a time."""

    time: dt.datetime
    """Time of the measurement, in UTC."""
    value: float
    """The value, in the unit of its quantity."""


@dataclass(frozen=True, slots=True)
class Series:
    """The readings of a quantity, from the oldest to the newest."""

    quantity: Quantity
    """The quantity measured."""
    readings: tuple[Reading, ...] = ()
    """The readings with a value, at strictly increasing times."""

    def __iter__(self) -> Iterator[Reading]:
        """Iterate over the readings, from the oldest."""
        return iter(self.readings)

    def __len__(self) -> int:
        """Return the number of readings."""
        return len(self.readings)

    @property
    def latest(self) -> Reading | None:
        """Return the newest reading; None when there is none."""
        return self.readings[-1] if self.readings else None

    def at(self, time: dt.datetime) -> Reading | None:
        """Return the reading measured at a time; None when there is none."""
        return next(
            (reading for reading in self.readings if reading.time == time), None
        )


@dataclass(frozen=True, slots=True)
class DailyExtremes:
    """Highest and lowest reading of a quantity today, from ``DATI_STAT``.

    Today is the Italian day: the extremes start again at midnight in
    Europe/Rome, they are not those of the last 24 hours.
    """

    quantity: Quantity
    """The quantity: level, temperature, humidity, gust or snow depth."""
    maximum: Reading | None
    """Highest reading since midnight."""
    minimum: Reading | None
    """Lowest reading since midnight."""


@dataclass(frozen=True, slots=True)
class StationData:
    """A station with its recent measurements: one file of Meteo 3R."""

    station: Station
    """The station, as its file describes it (thresholds included)."""
    series: tuple[Series, ...]
    """The series with at least one reading."""
    extremes: tuple[DailyExtremes, ...] = ()
    """The extremes of today, for the quantities that have them."""
    other_keys: tuple[str, ...] = ()
    """Series of the file aiometeo3r does not know, by key."""

    @property
    def quantities(self) -> frozenset[Quantity]:
        """Return the quantities with at least one reading."""
        return frozenset(series.quantity for series in self.series)

    def series_of(self, quantity: Quantity) -> Series:
        """Return the series of a quantity; an empty one when there is none."""
        return next(
            (series for series in self.series if series.quantity is quantity),
            Series(quantity),
        )

    def latest(self, quantity: Quantity) -> Reading | None:
        """Return the newest reading of a quantity; None when there is none."""
        return self.series_of(quantity).latest

    def extremes_of(self, quantity: Quantity) -> DailyExtremes | None:
        """Return the extremes of today of a quantity; None when not published."""
        return next((item for item in self.extremes if item.quantity is quantity), None)

    @property
    def level(self) -> Reading | None:
        """Return the newest water level; None without hydrometer or readings."""
        return self.latest(Quantity.LEVEL)

    @property
    def level_status(self) -> LevelStatus | None:
        """Return the newest level against the thresholds; None without a level."""
        level = self.level
        if level is None:
            return None
        return self.station.thresholds.status(level.value)
