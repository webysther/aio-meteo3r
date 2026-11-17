"""Tests of the models."""

from __future__ import annotations

import dataclasses
from enum import Enum

import pytest

from aiometeo3r import (
    LevelStatus,
    Quantity,
    Reading,
    SensorType,
    Series,
    Thresholds,
)
from aiometeo3r.parsers import parse_station_file

from . import PRAY, station_file, utc

CODED: tuple[type[SensorType | Quantity | LevelStatus], ...] = (
    SensorType,
    Quantity,
    LevelStatus,
)


@pytest.mark.parametrize("enum", CODED)
def test_codes(enum: type[SensorType | Quantity | LevelStatus]) -> None:
    """Test codes."""
    codes = [member.code for member in enum]

    assert len(set(codes)) == len(codes)
    assert all(enum.from_code(member.code) is member for member in enum)
    assert enum.from_code(-1) is None


def test_every_quantity_has_a_unit() -> None:
    """Test every quantity has a unit."""
    assert all(quantity.unit for quantity in Quantity)
    assert Quantity.WIND_SPEED.unit == "km/h"


@pytest.mark.parametrize(
    ("letter", "sensor"),
    [
        ("I", SensorType.HYDROMETER),
        ("p", SensorType.RAIN_GAUGE),
        ("G", SensorType.UNKNOWN),
        ("", SensorType.UNKNOWN),
    ],
)
def test_sensor_of_a_letter(letter: str, sensor: SensorType) -> None:
    """Test sensor of a letter."""
    assert SensorType.of(letter) is sensor


def test_level_status_prints_its_name() -> None:
    """Test level status prints its name."""
    assert str(LevelStatus.PRE_ALARM) == "pre_alarm"
    assert f"{LevelStatus.GUARD:>6}" == " guard"
    assert LevelStatus.DANGER > LevelStatus.GUARD


@pytest.mark.parametrize(
    ("thresholds", "level", "status"),
    [
        (Thresholds(2.3, 3.0, 3.8), 0.86, LevelStatus.NORMAL),
        (Thresholds(2.3, 3.0, 3.8), 2.3, LevelStatus.PRE_ALARM),
        (Thresholds(2.3, 3.0, 3.8), 3.5, LevelStatus.GUARD),
        (Thresholds(2.3, 3.0, 3.8), 4.0, LevelStatus.DANGER),
        (Thresholds(2.3, None, 3.8), 3.5, LevelStatus.PRE_ALARM),
        (Thresholds(None, None, 3.8), 3.5, LevelStatus.NORMAL),
        (Thresholds(), 3.5, LevelStatus.UNKNOWN),
    ],
)
def test_threshold_status(
    thresholds: Thresholds, level: float, status: LevelStatus
) -> None:
    """Test threshold status."""
    assert thresholds.status(level) is status


def test_series() -> None:
    """Test series."""
    first = Reading(utc(2026, 11, 17, 1), 0.86)
    second = Reading(utc(2026, 11, 17, 2), 0.87)
    series = Series(Quantity.LEVEL, (first, second))

    assert list(series) == [first, second]
    assert len(series) == 2
    assert series.latest == second
    assert series.at(utc(2026, 11, 17, 1)) == first
    assert series.at(utc(2026, 11, 17, 3)) is None
    assert Series(Quantity.LEVEL).latest is None


def test_station_data_is_a_value() -> None:
    """Test station data is a value."""
    first = parse_station_file(station_file(PRAY))
    second = parse_station_file(station_file(PRAY))

    assert first == second
    assert hash(first) == hash(second)
    with pytest.raises(dataclasses.FrozenInstanceError):
        first.station.name = "Other"  # type: ignore[misc]
    assert isinstance(Quantity.LEVEL, Enum)
