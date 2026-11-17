"""Fixtures of the aiometeo3r tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import trustme

from aiometeo3r import Meteo3rClient

from .server import FakeMeteo3r

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import aiohttp


@pytest.fixture(scope="session")
def ca() -> trustme.CA:
    """Return the certificate authority of the local server."""
    return trustme.CA()


@pytest.fixture
async def meteo3r(ca: trustme.CA) -> AsyncIterator[FakeMeteo3r]:
    """Run a local server answering for both hosts of Meteo 3R."""
    server = FakeMeteo3r(ca)
    await server.start()
    yield server
    await server.close()


@pytest.fixture
async def session(meteo3r: FakeMeteo3r) -> AsyncIterator[aiohttp.ClientSession]:
    """Return an aiohttp session reaching the local server."""
    async with meteo3r.client_session() as client_session:
        yield client_session


@pytest.fixture
def client(session: aiohttp.ClientSession) -> Meteo3rClient:
    """Return a client using the injected session."""
    return Meteo3rClient(session)
