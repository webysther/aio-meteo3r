"""Async client of the Meteo 3R measurements."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from functools import partial
from http import HTTPStatus
from typing import TYPE_CHECKING, Self

import aiohttp

from ._http import ConditionalCache
from .const import DEFAULT_REQUEST_TIMEOUT, HOST_RETRY_AFTER, REPOSITORY_URL
from .exceptions import (
    Meteo3rConnectionError,
    Meteo3rError,
    Meteo3rNotFoundError,
    Meteo3rParseError,
)
from .parsers import parse_registry, parse_station_file
from .urls import REGISTRY_PATH, Host, station_path

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from .models import Station, StationData

_LOGGER = logging.getLogger(__name__)


class Meteo3rClient:
    """Async client of the measurements of the Piedmont stations in Meteo 3R.

    Pass the ``aiohttp.ClientSession`` of the application (it is never closed
    by the client), or use the client as an async context manager to let it
    manage its own session.

    The files are on two hosts (:class:`Host`). Each request asks them in
    order and returns the first answer; a host that failed is asked last for
    :data:`HOST_RETRY_AFTER` seconds. Each host is asked whether the file
    changed since its last answer (``If-None-Match``, ``If-Modified-Since``):
    when it did not, the client returns the object it returned before, without
    downloading or parsing it again.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        *,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
        user_agent: str | None = None,
        hosts: Sequence[Host] = (Host.PRIMARY, Host.MIRROR),
    ) -> None:
        """Initialize the client.

        ``request_timeout`` applies to each request to a host, in seconds.
        ``user_agent`` names the application in the requests (default:
        aiometeo3r and its version). ``hosts`` are asked in order. Raises
        ``ValueError`` without hosts.
        """
        if not hosts:
            msg = "At least one host is needed"
            raise ValueError(msg)
        self._session = session
        self._close_session = False
        self._request_timeout = request_timeout
        self._user_agent = user_agent or _default_user_agent()
        self._hosts = tuple(Host(host) for host in hosts)
        self._failed_at: dict[Host, float] = {}
        self._active_host: Host | None = None
        self._registry: ConditionalCache[tuple[Station, ...]] = ConditionalCache()
        self._stations: ConditionalCache[StationData] = ConditionalCache()

    async def __aenter__(self) -> Self:
        """Enter the async context."""
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        """Exit the async context, closing the session owned by the client."""
        await self.close()

    @property
    def active_host(self) -> Host | None:
        """Return the host of the latest answer; None before the first one."""
        return self._active_host

    async def close(self) -> None:
        """Close the session if the client created it."""
        if self._session is not None and self._close_session:
            await self._session.close()
            self._session = None
            self._close_session = False

    async def get_stations(self) -> tuple[Station, ...]:
        """Return the stations of Piedmont.

        Meteo 3R writes the list again every 30 minutes (280 KB): read it to
        choose a station, not at every update.

        Raises :class:`Meteo3rConnectionError` or :class:`Meteo3rParseError`.
        """
        return await self._get(REGISTRY_PATH, parse_registry, self._registry)

    async def get_station_data(self, code: str) -> StationData:
        """Return a station of Piedmont with its readings of the last 3 days.

        ``code`` is the code of the station in the network (``"188"``).
        Raises ``ValueError`` for a code that is not letters and digits,
        :class:`Meteo3rNotFoundError` when Meteo 3R has no such station,
        :class:`Meteo3rConnectionError` or :class:`Meteo3rParseError`.
        """
        path = station_path(code)
        return await self._get(
            path, partial(parse_station_file, code=code), self._stations
        )

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            # Meteo 3R sets no cookie, the website of Arpa does: keep none.
            self._session = aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar())
            self._close_session = True
        return self._session

    def _host_order(self) -> list[Host]:
        """Return the hosts to ask, those that failed recently last."""
        now = time.monotonic()
        return sorted(
            self._hosts,
            key=lambda host: now - self._failed_at.get(host, -HOST_RETRY_AFTER)
            < HOST_RETRY_AFTER,
        )

    async def _get[T](
        self,
        path: str,
        parse: Callable[[object], T],
        cache: ConditionalCache[T],
    ) -> T:
        """Return a file parsed, from the first host that answers."""
        errors: list[Meteo3rError] = []
        for host in self._host_order():
            try:
                value = await self._fetch(host.url(path), parse, cache)
            except Meteo3rError as err:
                _LOGGER.debug("No answer from %s: %s", host.name, err)
                self._failed_at[host] = time.monotonic()
                errors.append(err)
            else:
                self._failed_at.pop(host, None)
                self._active_host = host
                return value
        raise _failure(path, errors) from errors[-1]

    async def _fetch[T](
        self, url: str, parse: Callable[[object], T], cache: ConditionalCache[T]
    ) -> T:
        """Return the file at a URL parsed, or the same object when unchanged."""
        session = self._get_session()
        headers = {"User-Agent": self._user_agent, **cache.validators(url)}
        _LOGGER.debug("Fetching %s", url)
        try:
            async with (
                asyncio.timeout(self._request_timeout),
                session.get(url, headers=headers) as response,
            ):
                if response.status == HTTPStatus.NOT_MODIFIED:
                    return _unchanged(url, cache)
                if response.status == HTTPStatus.NOT_FOUND:
                    msg = f"HTTP status 404 fetching {url}"
                    raise Meteo3rNotFoundError(msg)
                response.raise_for_status()
                body = await response.read()
                etag = response.headers.get(aiohttp.hdrs.ETAG)
                last_modified = response.headers.get(aiohttp.hdrs.LAST_MODIFIED)
        except TimeoutError as err:
            msg = f"Timeout fetching {url}"
            raise Meteo3rConnectionError(msg) from err
        except aiohttp.ClientResponseError as err:
            msg = f"HTTP status {err.status} fetching {url}"
            raise Meteo3rConnectionError(msg) from err
        except (aiohttp.ClientError, OSError) as err:
            msg = f"Error fetching {url}: {err!r}"
            raise Meteo3rConnectionError(msg) from err
        value = await asyncio.to_thread(_decode, url, body, parse)
        cache.store(url, value, etag=etag, last_modified=last_modified)
        return value


def _default_user_agent() -> str:
    from . import __version__  # noqa: PLC0415 - the package imports this module

    return f"aiometeo3r/{__version__} (+{REPOSITORY_URL})"


def _unchanged[T](url: str, cache: ConditionalCache[T]) -> T:
    """Return the previous answer of a URL the host says did not change."""
    value = cache.get(url)
    if value is None:
        msg = f"HTTP status 304 fetching {url}, without a previous answer"
        raise Meteo3rConnectionError(msg)
    return value


def _decode[T](url: str, body: bytes, parse: Callable[[object], T]) -> T:
    """Decode and parse a body: run in a worker thread, it can be 280 KB."""
    try:
        data: object = json.loads(body)
    except ValueError as err:
        msg = f"Invalid JSON from {url}"
        raise Meteo3rParseError(msg) from err
    return parse(data)


def _failure(path: str, errors: Sequence[Meteo3rError]) -> Meteo3rError:
    """Return the error of a file no host answered.

    Not found when every host said so; a parse error when a host answered
    something unreadable, which is how a change of the format shows; else a
    connection error.
    """
    detail = "; ".join(str(error) for error in errors)
    msg = f"No host answered {path}: {detail}"
    if all(isinstance(error, Meteo3rNotFoundError) for error in errors):
        return Meteo3rNotFoundError(msg)
    if any(isinstance(error, Meteo3rParseError) for error in errors):
        return Meteo3rParseError(msg)
    return Meteo3rConnectionError(msg)
