from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from subprocess import Popen

import pytest

from chai import Chai, NoServerConnection


# Fixture to start and clean up Apalache's Shai server
#
# - `autouse=True`:
#
#   Ensures that the fixture is provided (i.e., that the server is started)
#   for every test.
#
# - `scope="module"`:
#
#   Specifies that this fixture is created only once for all tests in the module,
#   rather than created once per test. See
#   https://docs.pytest.org/en/6.2.x/fixture.html#scope-sharing-fixtures-across-classes-modules-packages-or-session
@pytest.fixture(autouse=True, scope="module")
def server() -> Iterator[Popen]:
    # TODO Pass port to server explicitly when that is supported
    process = Popen(["apalache-mc", "server"])
    yield process
    process.terminate()


# Fixture to provide and clean up a connected client for each test
#
# NOTE: In contrast to the `server` fixture, we do want to create this once for
# each test
@pytest.fixture
async def client(server: Popen) -> AsyncIterator[Chai]:
    # We need to ensure the server is created before we create the client
    _ = server
    async with Chai.create() as client:
        yield client


async def test_can_obtain_a_connection(client: Chai) -> None:
    assert client.is_connected()


async def test_raises_error_after_timeout() -> None:
    # configure the client to use a non-existent server
    client = Chai(domain="invalid.domain", port=6666, timeout=0.5)
    try:
        with pytest.raises(NoServerConnection):
            await client.connect()
    finally:
        await client.close()
