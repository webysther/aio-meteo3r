"""Local HTTPS server standing in for the Meteo 3R hosts.

A fake DNS resolver sends the hosts to a local aiohttp test server whose
certificate is issued by a test CA, so the client runs unchanged against real
aiohttp responses (pattern of aiohttp's "fake server" example).
"""

from __future__ import annotations

import asyncio
import socket
import ssl
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from aiohttp import ClientSession, DummyCookieJar, TCPConnector, web
from aiohttp.abc import AbstractResolver, ResolveResult
from aiohttp.test_utils import TestServer
from multidict import CIMultiDictProxy

if TYPE_CHECKING:
    import trustme

HOSTS = ("staticm3r.arpa.piemonte.it", "www.meteo3r.it")


@dataclass(frozen=True, slots=True)
class Route:
    """Response served for a URL.

    With ``etag`` or ``last_modified``, the server sends them and answers 304
    to a request that has them (``If-None-Match``, ``If-Modified-Since``).
    """

    body: str | bytes = b""
    status: int = 200
    etag: str | None = None
    last_modified: str | None = None
    before: Callable[[], Awaitable[None]] | None = None
    disconnect: bool = False


@dataclass(frozen=True, slots=True)
class Request:
    """A request the server received."""

    url: str
    headers: CIMultiDictProxy[str]


class FakeResolver(AbstractResolver):
    """Resolve the hosts to the local server and fail for unknown hosts."""

    def __init__(self, port: int, unresolvable: set[str]) -> None:
        """Initialize the resolver."""
        self._port = port
        self._unresolvable = unresolvable

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        """Return the address of the local server."""
        del port, family
        if host not in HOSTS or host in self._unresolvable:
            msg = f"Name or service not known: {host}"
            raise OSError(msg)
        return [
            {
                "hostname": host,
                "host": "127.0.0.1",
                "port": self._port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": socket.AI_NUMERICHOST,
            }
        ]

    async def close(self) -> None:
        """Release the resolver."""


class FakeMeteo3r:
    """Local server answering the configured URLs of both hosts.

    Unknown URLs answer 404. Every request is recorded in ``requests``.
    """

    def __init__(self, ca: trustme.CA) -> None:
        """Initialize the server."""
        self._ca = ca
        self._routes: dict[str, Route] = {}
        self._released = asyncio.Event()
        self._server: TestServer | None = None
        self.unresolvable: set[str] = set()
        self.requests: list[Request] = []

    @property
    def urls(self) -> list[str]:
        """Return the URLs requested, in order."""
        return [request.url for request in self.requests]

    def add(
        self,
        url: str,
        *,
        body: str | bytes = b"",
        status: int = 200,
        etag: str | None = None,
        last_modified: str | None = None,
        before: Callable[[], Awaitable[None]] | None = None,
        disconnect: bool = False,
    ) -> None:
        """Serve a response for a URL, replacing any previous one."""
        self._routes[url] = Route(body, status, etag, last_modified, before, disconnect)

    async def hang(self) -> None:
        """Wait until the server closes (to simulate a stalled response)."""
        await self._released.wait()

    async def start(self) -> None:
        """Start the server."""
        app = web.Application()
        app.router.add_route("GET", "/{path:.*}", self._handle)
        server_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self._ca.issue_cert(*HOSTS).configure_cert(server_context)
        self._server = TestServer(app)
        await self._server.start_server(ssl=server_context)

    async def close(self) -> None:
        """Release the stalled responses and stop the server."""
        self._released.set()
        if self._server is not None:
            await self._server.close()

    def client_session(self, **kwargs: object) -> ClientSession:
        """Return a session whose requests to the hosts reach this server."""
        assert self._server is not None
        assert self._server.port is not None
        client_context = ssl.create_default_context()
        self._ca.configure_trust(client_context)
        connector = TCPConnector(
            resolver=FakeResolver(self._server.port, self.unresolvable),
            ssl=client_context,
        )
        cookie_jar = kwargs.get("cookie_jar")
        # Bound at import time: tests may replace aiohttp.ClientSession.
        if isinstance(cookie_jar, DummyCookieJar):
            return ClientSession(connector=connector, cookie_jar=cookie_jar)
        return ClientSession(connector=connector)

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        url = str(request.url.with_port(None))
        self.requests.append(Request(url, request.headers))
        route = self._routes.get(url)
        if route is None:
            return web.Response(status=404, text="404: Not Found")
        if route.before is not None:
            await route.before()
        if route.disconnect:
            assert request.transport is not None
            request.transport.close()
        headers = {}
        if route.etag is not None:
            headers["ETag"] = route.etag
        if route.last_modified is not None:
            headers["Last-Modified"] = route.last_modified
        if headers and (
            (route.etag and request.headers.get("If-None-Match") == route.etag)
            or (
                route.last_modified
                and request.headers.get("If-Modified-Since") == route.last_modified
            )
        ):
            return web.Response(status=304, headers=headers)
        return web.Response(status=route.status, body=route.body, headers=headers)
