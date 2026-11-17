"""Tests of the parsing of the Meteo 3R files."""

from __future__ import annotations

import datetime as dt
import math

import pytest

from aiometeo3r import (
    LevelStatus,
    Meteo3rParseError,
    Quantity,
    Reading,
    SensorType,
    Thresholds,
)
from aiometeo3r.parsers import (
    parse_decimal,
    parse_registry,
    parse_station,
    parse_station_file,
    rome_times_to_utc,
)

from . import COLLE_LOMBARDA, MALCIAUSSIA, PRAY, real_json, station_file, utc

RECORD: dict[str, object] = {
    "IDRETE": "PIE",
    "CODSTAZ": "188",
    "DENOMINAZIONE": "Pray Sessera",
    "LAT": 45.67389,
    "LON": 8.22167,
    "TIPO": "IPT",
    "ISTAT": "096050",
    "COMUNE": "Pray",
    "PROVINCIA": "PROVINCIA DI BIELLA",
    "SIGLA_PROVINCIA": "BI",
    "REGIONE": "PIEMONTE",
    "QUOTA": 409.0,
    "CORSO_ACQUA": "SESSERA",
    "ZERO_IDROMETRICO": "400.70",
    "SOGLIA_PRE": "2.3",
    "SOGLIA_GUARDIA": "3.0",
    "SOGLIA_PERICOLO": "3.8",
    "BACINO_PLUV": "SESIA",
    "NOTE_STAZ": "",
    "IDRETE_CODSTAZ": "PIE_188",
}


def synthetic(
    times: list[str], statistics: dict[str, object] | None = None, **series: object
) -> dict[str, object]:
    """Return a station file of Pray with the given readings."""
    return {
        "IDRETE_CODSTAZ": "PIE_188",
        "ANAGRAFICA": RECORD,
        "DATI": {"DATA_ORA": times, **series},
        "DATI_STAT": statistics or {},
    }


class TestRegistry:
    """The station list."""

    def test_real_list_has_the_stations_of_piedmont_only(self) -> None:
        """Test real list has the stations of piedmont only."""
        stations = parse_registry(real_json("misureAnagrafica.json"))

        assert len(stations) == 374
        assert len({station.code for station in stations}) == 374
        assert sum(station.has(SensorType.HYDROMETER) for station in stations) == 110
        assert all(station.id.startswith("PIE_") for station in stations)

    def test_real_station(self) -> None:
        """Test real station."""
        stations = parse_registry(real_json("misureAnagrafica.json"))
        pray = next(station for station in stations if station.code == PRAY)

        assert pray.name == "Pray Sessera"
        assert pray.id == "PIE_188"
        assert pray.river == "SESSERA"
        assert pray.basin == "SESIA"
        assert pray.municipality_code == "096050"
        assert pray.province_code == "BI"
        assert pray.altitude == 409.0
        assert pray.hydrometric_zero == 400.7
        assert pray.thresholds == Thresholds(2.3, 3.0, 3.8)
        assert pray.sensor_types == {
            SensorType.HYDROMETER,
            SensorType.RAIN_GAUGE,
            SensorType.THERMOMETER,
        }
        assert pray.note is None

    def test_leading_zeros_are_kept(self) -> None:
        """Test leading zeros are kept."""
        stations = parse_registry(real_json("misureAnagrafica.json"))

        assert COLLE_LOMBARDA in {station.code for station in stations}

    def test_unreadable_records_are_left_out(self) -> None:
        """Test unreadable records are left out."""
        stations = parse_registry(
            [
                RECORD,
                "not a record",
                {**RECORD, "CODSTAZ": "189", "DENOMINAZIONE": ""},
                {**RECORD, "CODSTAZ": "190", "LAT": "45.6"},
                {**RECORD, "IDRETE": "LIG", "CODSTAZ": "AIROL"},
            ]
        )

        assert [station.code for station in stations] == ["188"]

    @pytest.mark.parametrize(
        "data", [{"stations": []}, [], [{**RECORD, "IDRETE": "VDA"}]]
    )
    def test_no_station_of_piedmont(self, data: object) -> None:
        """Test no station of piedmont."""
        with pytest.raises(Meteo3rParseError):
            parse_registry(data)


class TestStation:
    """A station record."""

    def test_letters_in_any_order(self) -> None:
        """Test letters in any order."""
        first = parse_station({**RECORD, "TIPO": "IPT"})
        second = parse_station({**RECORD, "TIPO": "TPI"})

        assert first.sensor_types == second.sensor_types
        assert second.sensor_letters == "TPI"

    def test_unknown_letter(self) -> None:
        """Test unknown letter."""
        station = parse_station({**RECORD, "TIPO": "BGHPRTV"})

        assert SensorType.UNKNOWN in station.sensor_types
        assert SensorType.BAROMETER in station.sensor_types
        assert station.sensor_letters == "BGHPRTV"

    def test_missing_values(self) -> None:
        """Test missing values."""
        station = parse_station(
            {
                **RECORD,
                "TIPO": None,
                "QUOTA": True,
                "CORSO_ACQUA": "-",
                "ZERO_IDROMETRICO": "",
                "SOGLIA_PRE": "",
                "SOGLIA_GUARDIA": None,
                "SOGLIA_PERICOLO": "2",
                "NOTE_STAZ": " Dati neve annullati ",
                "COMUNE": None,
            }
        )

        assert station.sensor_types == frozenset()
        assert station.altitude is None
        assert station.river is None
        assert station.hydrometric_zero is None
        assert station.thresholds == Thresholds(None, None, 2.0)
        assert station.note == "Dati neve annullati"
        assert station.municipality == ""

    def test_infinite_altitude(self) -> None:
        """Test infinite altitude."""
        assert parse_station({**RECORD, "QUOTA": math.inf}).altitude is None

    @pytest.mark.parametrize(
        "change",
        [{"CODSTAZ": None}, {"DENOMINAZIONE": "  "}, {"LAT": None}, {"LON": "8"}],
    )
    def test_required_values(self, change: dict[str, object]) -> None:
        """Test required values."""
        with pytest.raises(Meteo3rParseError):
            parse_station({**RECORD, **change})


class TestStationFile:
    """A station file."""

    def test_pray(self) -> None:
        """Test pray."""
        data = parse_station_file(station_file(PRAY), PRAY)

        assert data.station.name == "Pray Sessera"
        assert data.quantities == {
            Quantity.LEVEL,
            Quantity.TEMPERATURE,
            Quantity.RAIN_1H,
            Quantity.RAIN_3H,
            Quantity.RAIN_24H,
        }
        # I_LAST and I_LAST_DATA of DATI_STAT: 0.86 at 03:00 Italian time
        assert data.level == Reading(utc(2026, 11, 17, 2), 0.86)
        assert data.level_status is LevelStatus.NORMAL
        level = data.series_of(Quantity.LEVEL)
        assert len(level) == 153
        times = [reading.time for reading in level]
        assert times == sorted(times)
        assert times[0] == utc(2026, 11, 13, 22)
        assert all(time.tzinfo is dt.UTC for time in times)
        assert data.other_keys == ()

    def test_extremes_of_today(self) -> None:
        """Test extremes of today."""
        data = parse_station_file(station_file(PRAY))

        level = data.extremes_of(Quantity.LEVEL)
        assert level is not None
        # Since midnight Italian time, not over 24 hours
        assert level.maximum == Reading(utc(2026, 11, 16, 23), 0.88)
        assert level.minimum == Reading(utc(2026, 11, 17, 0, 30), 0.86)
        assert data.extremes_of(Quantity.HUMIDITY) is None

    def test_colle_lombarda(self) -> None:
        """Test colle lombarda."""
        data = parse_station_file(station_file(COLLE_LOMBARDA))

        assert Quantity.WIND_SPEED in data.quantities
        assert data.latest(Quantity.GUST_SPEED) == Reading(utc(2026, 11, 17, 2), 16.9)
        # Read once a day at 08:00 Italian time
        assert data.latest(Quantity.DAILY_SNOW_DEPTH) == Reading(
            utc(2026, 11, 16, 7), 6.0
        )
        assert len(data.series_of(Quantity.DAILY_SNOW_DEPTH)) == 7
        assert {item.quantity for item in data.extremes} == {
            Quantity.TEMPERATURE,
            Quantity.HUMIDITY,
            Quantity.GUST_SPEED,
            Quantity.SNOW_DEPTH,
        }
        assert data.level is None
        assert data.level_status is None

    def test_station_without_readings(self) -> None:
        """Test station without readings."""
        data = parse_station_file(station_file(MALCIAUSSIA))

        assert data.series == ()
        assert data.extremes == ()
        assert data.latest(Quantity.SNOW_DEPTH) is None
        assert len(data.series_of(Quantity.SNOW_DEPTH)) == 0

    def test_null_and_non_finite_values_are_not_readings(self) -> None:
        """Test null and non finite values are not readings."""
        data = parse_station_file(
            synthetic(
                ["2026-11-17 02:00", "2026-11-17 02:30", "2026-11-17 03:00"],
                I=[0.86, math.nan, None],
                T=[None, None, None],
                I_STATO=[0.0, 0.0, 4.0],
            )
        )

        assert data.series_of(Quantity.LEVEL).readings == (
            Reading(utc(2026, 11, 17, 1), 0.86),
        )
        assert data.quantities == {Quantity.LEVEL}

    def test_unknown_series_are_listed(self) -> None:
        """Test unknown series are listed."""
        data = parse_station_file(
            synthetic(["2026-11-17 02:00"], I=[1], RAD=[300.0], I_STATO=[0.0])
        )

        assert data.other_keys == ("RAD",)
        assert data.level == Reading(utc(2026, 11, 17, 1), 1.0)

    def test_file_without_readings_or_statistics(self) -> None:
        """Test a file with the station only."""
        data = parse_station_file({"ANAGRAFICA": RECORD})

        assert data.series == ()
        assert data.extremes == ()

    def test_reading_at_a_skipped_time(self) -> None:
        """Test that a reading at a time that does not exist is left out."""
        data = parse_station_file(
            synthetic(["2027-03-28 01:30", "2027-03-28 02:30"], I=[1.0, 2.0])
        )

        assert data.series_of(Quantity.LEVEL).readings == (
            Reading(utc(2027, 3, 28, 0, 30), 1.0),
        )

    def test_wrong_station(self) -> None:
        """Test wrong station."""
        with pytest.raises(Meteo3rParseError, match="station 188"):
            parse_station_file(station_file(PRAY), "189")

    @pytest.mark.parametrize(
        "data",
        [
            [],
            {"ANAGRAFICA": "PIE_188"},
            {"ANAGRAFICA": RECORD, "DATI": []},
            {"ANAGRAFICA": RECORD, "DATI": {}, "DATI_STAT": []},
            synthetic("2026-11-17 02:00"),  # type: ignore[arg-type]
            synthetic([None]),  # type: ignore[list-item]
            synthetic(["17/11/2026 02:00"]),
            synthetic(["2026-11-17 02:00"], I="0.86"),
            synthetic(["2026-11-17 02:00"], I=[0.86, 0.87]),
            synthetic(["2026-11-17 02:00"], I=["0.86"]),
            synthetic(["2026-11-17 02:00"], I=[True]),
            synthetic(["2026-11-17 02:00"], HS_V=[3.0]),
        ],
    )
    def test_unexpected_format(self, data: object) -> None:
        """Test unexpected format."""
        with pytest.raises(Meteo3rParseError):
            parse_station_file(data)

    def test_statistics_without_time_or_value(self) -> None:
        """Test statistics without time or value."""
        data = parse_station_file(
            synthetic(
                ["2026-11-17 02:00"],
                {"I_MAX": 1.0, "I_MIN": None, "I_MIN_DATA": "2026-11-17 02:00"},
                I=[1.0],
            )
        )

        assert data.extremes == ()

    def test_statistics_time_outside_the_readings(self) -> None:
        """Test statistics time outside the readings."""
        data = parse_station_file(
            synthetic(
                ["2026-11-17 02:00"],
                {"T_MAX": 2.0, "T_MAX_DATA": "2026-11-17 00:00"},
                I=[1.0],
            )
        )

        extremes = data.extremes_of(Quantity.TEMPERATURE)
        assert extremes is not None
        assert extremes.maximum == Reading(utc(2026, 11, 16, 23), 2.0)
        assert extremes.minimum is None


# Summer time ends on 2026-10-25 at 03:00 (02:00-03:00 twice) and starts on
# 2027-03-28 at 02:00 (02:00-03:00 skipped).
FALL_BACK_WITH_REPEAT = [
    "2026-10-25 01:30",
    "2026-10-25 02:00",
    "2026-10-25 02:30",
    "2026-10-25 02:00",
    "2026-10-25 02:30",
    "2026-10-25 03:00",
]


class TestItalianTimes:
    """Italian times without offset, placed as instants."""

    def test_winter_and_summer_time(self) -> None:
        """Test winter and summer time."""
        assert rome_times_to_utc(["2026-11-17 03:00", "2026-11-17 03:30"]) == [
            utc(2026, 11, 17, 2),
            utc(2026, 11, 17, 2, 30),
        ]
        assert rome_times_to_utc(["2026-07-01 12:00"]) == [utc(2026, 7, 1, 10)]

    def test_repeated_hour_when_summer_time_ends(self) -> None:
        """Test repeated hour when summer time ends."""
        assert rome_times_to_utc(FALL_BACK_WITH_REPEAT) == [
            utc(2026, 10, 24, 23, 30),
            utc(2026, 10, 25, 0),
            utc(2026, 10, 25, 0, 30),
            utc(2026, 10, 25, 1),
            utc(2026, 10, 25, 1, 30),
            utc(2026, 10, 25, 2),
        ]

    def test_hour_written_once_when_summer_time_ends(self) -> None:
        """Test hour written once when summer time ends."""
        assert rome_times_to_utc(
            ["2026-10-25 02:00", "2026-10-25 02:30", "2026-10-25 03:00"]
        ) == [utc(2026, 10, 25, 0), utc(2026, 10, 25, 0, 30), utc(2026, 10, 25, 2)]

    def test_latest_reading_of_the_repeated_hour_is_not_in_the_future(self) -> None:
        # At 02:45 summer time, the latest reading is the first 02:30.
        """Test latest reading of the repeated hour is not in the future."""
        assert rome_times_to_utc(["2026-10-25 02:00", "2026-10-25 02:30"])[-1] == utc(
            2026, 10, 25, 0, 30
        )

    def test_skipped_hour_when_summer_time_starts(self) -> None:
        """Test skipped hour when summer time starts."""
        assert rome_times_to_utc(
            [
                "2027-03-28 01:30",
                "2027-03-28 02:00",
                "2027-03-28 02:30",
                "2027-03-28 03:00",
            ]
        ) == [utc(2027, 3, 28, 0, 30), None, None, utc(2027, 3, 28, 1)]

    def test_times_that_do_not_advance(self) -> None:
        """Test times that do not advance."""
        assert rome_times_to_utc(
            [
                "2026-11-17 03:00",
                "2026-11-17 03:00",
                "2026-11-17 02:30",
                "2026-11-17 03:30",
            ]
        ) == [utc(2026, 11, 17, 2), None, None, utc(2026, 11, 17, 2, 30)]

    def test_readings_of_the_repeated_hour(self) -> None:
        """Test readings of the repeated hour."""
        data = parse_station_file(
            synthetic(
                FALL_BACK_WITH_REPEAT,
                {
                    # 02:00 twice: the extreme is the second one, by its value
                    "I_MAX": 1.4,
                    "I_MAX_DATA": "2026-10-25 02:00",
                    "I_MIN": 1.0,
                    "I_MIN_DATA": "2026-10-25 01:30",
                    # Not a series of the file: the latest of the repeated hour
                    "T_MAX": 9.0,
                    "T_MAX_DATA": "2026-10-25 02:30",
                    # No reading has this value: the latest of the repeated hour
                    "HS_MAX": 4.0,
                    "HS_MAX_DATA": "2026-10-25 02:00",
                    # A skipped time outside the readings
                    "RH_MAX": 90.0,
                    "RH_MAX_DATA": "2027-03-28 02:30",
                },
                I=[1.0, 1.2, 1.3, 1.4, 1.3, 1.2],
                HS=[3.0, 3.0, 3.0, 3.0, 3.0, 3.0],
            )
        )

        level = data.extremes_of(Quantity.LEVEL)
        assert level is not None
        assert level.maximum == Reading(utc(2026, 10, 25, 1), 1.4)
        assert level.minimum == Reading(utc(2026, 10, 24, 23, 30), 1.0)
        snow = data.extremes_of(Quantity.SNOW_DEPTH)
        assert snow is not None
        assert snow.maximum == Reading(utc(2026, 10, 25, 1), 4.0)
        humidity = data.extremes_of(Quantity.HUMIDITY)
        assert humidity is not None
        assert humidity.maximum is not None
        assert humidity.maximum.time == utc(2027, 3, 28, 1, 30)


@pytest.mark.parametrize(
    ("value", "number"),
    [
        ("2.3", 2.3),
        ("3", 3.0),
        ("3.0", 3.0),
        (" 2,5 ", 2.5),
        (2, 2.0),
        (400.7, 400.7),
        ("", None),
        ("-", None),
        ("n/d", None),
        ("nan", None),
        ("inf", None),
        (math.inf, None),
        (True, None),
        (None, None),
        ([], None),
    ],
)
def test_parse_decimal(value: object, number: float | None) -> None:
    """Test parse decimal."""
    assert parse_decimal(value) == number
