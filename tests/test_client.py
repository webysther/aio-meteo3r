"""Tests of the client against the local server standing in for Meteo 3R."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import aiohttp
import pytest

from aiometeo3r import (
    HOST_RETRY_AFTER,
    Host,
    Meteo3rClient,
    Meteo3rConnectionError,
    Meteo3rNotFoundError,
    Meteo3rParseError,
    __version__,
)

from . import (
    MIRROR_REGISTRY_URL,
    PRAY,
    REGISTRY_URL,
    real_bytes,
    station_url,
)

if TYPE_CHECKING:
    from .server import FakeMeteo3r

PRAY_FILE = real_bytes("misure_PIE_188.json")
ETAG = 'W/"6afbb104-3838"'
LAST_MODIFIED = "Tue, 17 Nov 2026 01:42:28 GMT"
MIRROR_LAST_MODIFIED = "Tue, 17 Nov 2026 01:35:20 GMT"


def serve_pray(
    meteo3r: FakeMeteo3r, host: Host = Host.PRIMARY, **kwargs: object
) -> str:
    """Serve the file of Pray on a host; return its URL."""
    url = station_url(PRAY, host)
    meteo3r.add(url, body=PRAY_FILE, **kwargs)  # type: ignore[arg-type]
    return url


async def test_station_data(client: Meteo3rClient, meteo3r: FakeMeteo3r) -> None:
    """Test station data."""
    url = serve_pray(meteo3r)

    data = await client.get_station_data(PRAY)

    assert data.station.name == "Pray Sessera"
    assert data.level is not None
    assert meteo3r.urls == [url]
    assert client.active_host is Host.PRIMARY


async def test_stations(client: Meteo3rClient, meteo3r: FakeMeteo3r) -> None:
    """Test stations."""
    meteo3r.add(REGISTRY_URL, body=real_bytes("misureAnagrafica.json"))

    stations = await client.get_stations()

    assert len(stations) == 374


async def test_user_agent(session: aiohttp.ClientSession, meteo3r: FakeMeteo3r) -> None:
    """Test user agent."""
    serve_pray(meteo3r)

    await Meteo3rClient(session).get_station_data(PRAY)
    await Meteo3rClient(session, user_agent="MyApp/1.0").get_station_data(PRAY)

    agents = [request.headers["User-Agent"] for request in meteo3r.requests]
    assert agents[0].startswith(f"aiometeo3r/{__version__} (+https://")
    assert agents[1] == "MyApp/1.0"


async def test_unchanged_file_is_not_parsed_again(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test unchanged file is not parsed again."""
    serve_pray(meteo3r, etag=ETAG, last_modified=LAST_MODIFIED)

    first = await client.get_station_data(PRAY)
    second = await client.get_station_data(PRAY)

    assert second is first
    request = meteo3r.requests[1]
    assert request.headers["If-None-Match"] == ETAG
    assert request.headers["If-Modified-Since"] == LAST_MODIFIED


async def test_changed_file(client: Meteo3rClient, meteo3r: FakeMeteo3r) -> None:
    """Test changed file."""
    serve_pray(meteo3r, etag=ETAG)
    first = await client.get_station_data(PRAY)
    serve_pray(meteo3r, etag='W/"6afbb200-3840"')

    second = await client.get_station_data(PRAY)

    assert second is not first
    assert second == first


async def test_file_without_validators_is_downloaded_again(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test file without validators is downloaded again."""
    serve_pray(meteo3r)

    await client.get_station_data(PRAY)
    await client.get_station_data(PRAY)

    assert "If-Modified-Since" not in meteo3r.requests[1].headers


async def test_unexpected_not_modified(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test unexpected not modified."""
    serve_pray(meteo3r, status=304)
    serve_pray(meteo3r, Host.MIRROR, status=304)

    with pytest.raises(Meteo3rConnectionError, match="without a previous answer"):
        await client.get_station_data(PRAY)


@pytest.mark.parametrize(
    "failure",
    [
        {"status": 500},
        {"status": 503},
        {"body": b"<!doctype html><html></html>"},
        {"body": b'{"IDRETE_CODSTAZ": "PIE_188"}'},
        {"status": 404},
        {"disconnect": True},
    ],
)
async def test_mirror_answers_when_the_primary_fails(
    client: Meteo3rClient, meteo3r: FakeMeteo3r, failure: dict[str, object]
) -> None:
    """Test mirror answers when the primary fails."""
    primary = station_url(PRAY)
    meteo3r.add(primary, **failure)  # type: ignore[arg-type]
    mirror = serve_pray(meteo3r, Host.MIRROR)

    data = await client.get_station_data(PRAY)

    assert data.station.code == PRAY
    # aiohttp asks once more after a disconnection
    assert meteo3r.urls[0] == primary
    assert meteo3r.urls[-1] == mirror
    assert client.active_host is Host.MIRROR


async def test_mirror_answers_when_the_primary_is_unreachable(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test mirror answers when the primary is unreachable."""
    meteo3r.unresolvable.add("staticm3r.arpa.piemonte.it")
    mirror = serve_pray(meteo3r, Host.MIRROR)

    await client.get_station_data(PRAY)

    assert meteo3r.urls == [mirror]


async def test_mirror_answers_when_the_primary_times_out(
    session: aiohttp.ClientSession, meteo3r: FakeMeteo3r
) -> None:
    """Test mirror answers when the primary times out."""
    client = Meteo3rClient(session, request_timeout=0.1)
    serve_pray(meteo3r, before=meteo3r.hang)
    serve_pray(meteo3r, Host.MIRROR)

    await client.get_station_data(PRAY)

    assert client.active_host is Host.MIRROR


async def test_failed_host_is_asked_last_for_a_while(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test failed host is asked last for a while."""
    primary = serve_pray(meteo3r, status=500)
    mirror = serve_pray(meteo3r, Host.MIRROR)
    await client.get_station_data(PRAY)

    await client.get_station_data(PRAY)
    assert meteo3r.urls == [primary, mirror, mirror]

    client._failed_at[Host.PRIMARY] -= HOST_RETRY_AFTER
    serve_pray(meteo3r)
    await client.get_station_data(PRAY)
    assert meteo3r.urls[-1] == primary
    assert client.active_host is Host.PRIMARY
    assert Host.PRIMARY not in client._failed_at


async def test_each_host_is_asked_with_its_own_validators(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test each host is asked with its own validators."""
    serve_pray(meteo3r, etag=ETAG, last_modified=LAST_MODIFIED)
    serve_pray(meteo3r, Host.MIRROR, last_modified=MIRROR_LAST_MODIFIED)
    await client.get_station_data(PRAY)
    client._hosts = (Host.MIRROR, Host.PRIMARY)

    await client.get_station_data(PRAY)
    await client.get_station_data(PRAY)

    first, second = meteo3r.requests[1:]
    assert "If-None-Match" not in first.headers
    assert "If-Modified-Since" not in first.headers
    assert second.headers["If-Modified-Since"] == MIRROR_LAST_MODIFIED


async def test_station_not_found(client: Meteo3rClient, meteo3r: FakeMeteo3r) -> None:
    """Test station not found."""
    with pytest.raises(Meteo3rNotFoundError, match="No host answered"):
        await client.get_station_data("999")

    assert len(meteo3r.urls) == 2


async def test_unreadable_answer_is_a_parse_error(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test unreadable answer is a parse error."""
    meteo3r.add(REGISTRY_URL, body=b"{not json")
    meteo3r.add(MIRROR_REGISTRY_URL, status=500)

    with pytest.raises(Meteo3rParseError, match="Invalid JSON"):
        await client.get_stations()


@pytest.mark.parametrize("body", [b"\xff\xfe\xfd", b"", b"[]"])
async def test_invalid_bodies(
    client: Meteo3rClient, meteo3r: FakeMeteo3r, body: bytes
) -> None:
    """Test invalid bodies."""
    meteo3r.add(REGISTRY_URL, body=body)
    meteo3r.add(MIRROR_REGISTRY_URL, body=body)

    with pytest.raises(Meteo3rParseError):
        await client.get_stations()


async def test_no_host_answers(client: Meteo3rClient, meteo3r: FakeMeteo3r) -> None:
    """Test no host answers."""
    meteo3r.add(REGISTRY_URL, status=500)
    meteo3r.unresolvable.add("www.meteo3r.it")

    with pytest.raises(Meteo3rConnectionError) as error:
        await client.get_stations()

    assert "HTTP status 500" in str(error.value)
    assert isinstance(error.value.__cause__, Meteo3rConnectionError)
    assert isinstance(error.value.__cause__.__cause__, aiohttp.ClientConnectorError)


async def test_cancellation_propagates(
    client: Meteo3rClient, meteo3r: FakeMeteo3r
) -> None:
    """Test cancellation propagates."""
    started = asyncio.Event()

    async def hang() -> None:
        started.set()
        await meteo3r.hang()

    serve_pray(meteo3r, before=hang)
    task = asyncio.create_task(client.get_station_data(PRAY))
    await started.wait()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize("code", ["", "18 8", "../188", "PIE_188"])
async def test_invalid_code_is_checked_before_any_request(
    client: Meteo3rClient, meteo3r: FakeMeteo3r, code: str
) -> None:
    """Test invalid code is checked before any request."""
    with pytest.raises(ValueError, match="Invalid station code"):
        await client.get_station_data(code)

    assert meteo3r.requests == []


def test_hosts_are_needed() -> None:
    """Test hosts are needed."""
    with pytest.raises(ValueError, match="host"):
        Meteo3rClient(hosts=())


async def test_own_session_is_closed(
    meteo3r: FakeMeteo3r, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test own session is closed."""
    sessions: list[aiohttp.ClientSession] = []

    def session_factory(**kwargs: object) -> aiohttp.ClientSession:
        assert isinstance(kwargs["cookie_jar"], aiohttp.DummyCookieJar)
        sessions.append(meteo3r.client_session(**kwargs))
        return sessions[-1]

    monkeypatch.setattr(aiohttp, "ClientSession", session_factory)
    serve_pray(meteo3r)

    async with Meteo3rClient() as client:
        await client.get_station_data(PRAY)
        await client.get_station_data(PRAY)

    assert len(sessions) == 1
    assert sessions[0].closed
    await client.close()


async def test_injected_session_is_not_closed(
    session: aiohttp.ClientSession, meteo3r: FakeMeteo3r
) -> None:
    """Test injected session is not closed."""
    serve_pray(meteo3r)

    async with Meteo3rClient(session) as client:
        await client.get_station_data(PRAY)

    assert not session.closed


async def test_close_without_requests() -> None:
    """Test close without requests."""
    client = Meteo3rClient()

    await client.close()

    assert client.active_host is None
