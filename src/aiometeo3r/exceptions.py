"""Exceptions raised by aiometeo3r."""

from __future__ import annotations


class Meteo3rError(Exception):
    """Base class of the aiometeo3r errors."""


class Meteo3rConnectionError(Meteo3rError):
    """No host answered: network error, HTTP error status or timeout."""


class Meteo3rParseError(Meteo3rError):
    """A host answered with data that is not valid JSON or has an unexpected format.

    Meteo 3R has no documented format: this is how a change of the app shows.
    """


class Meteo3rNotFoundError(Meteo3rError):
    """Every host answered 404: the file does not exist.

    For the measurements of a station, Meteo 3R has no station with that code,
    so retrying does not help.
    """
