from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from subprocess import Popen

import pytest

from chai import (
    ChaiTransExplorer,
    LoadModuleErr,
    NoServerConnection,
    RpcCallWithoutConnection,
)


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
async def client(server: Popen) -> AsyncIterator[ChaiTransExplorer]:
    # We need to ensure the server is created before we create the client
    _ = server
    async with ChaiTransExplorer.create() as client:
        yield client


async def test_can_obtain_a_connection(client: ChaiTransExplorer) -> None:
    assert client.is_connected()


async def test_raises_error_after_timeout() -> None:
    # configure the client to use a non-existent server
    client = ChaiTransExplorer(domain="invalid.domain", port=6666, timeout=0.5)
    try:
        with pytest.raises(NoServerConnection):
            await client.connect()
    finally:
        await client.close()


async def test_can_load_model(client: ChaiTransExplorer) -> None:
    spec = """
---- MODULE M ----
Foo == TRUE
====
"""
    res = await client.load_model(spec)
    assert isinstance(res, dict)
    m = res["modules"][0]
    assert m["name"] == "M" and m["kind"] == "TlaModule"


async def test_can_load_model_with_aux_modules(client: ChaiTransExplorer) -> None:
    spec = """
---- MODULE M ----
EXTENDS A
Foo == FooA
====
"""
    aux = [
        """
---- MODULE A ----
FooA == TRUE
====
"""
    ]
    res = await client.load_model(spec, aux)
    assert isinstance(res, dict)
    m = res["modules"][0]
    assert any(d["name"] == "FooA" for d in m["declarations"])


async def test_loading_invalid_model_gives_error(client: ChaiTransExplorer) -> None:
    spec = """
---- missing module declaration ----
Foo == TRUE
====
"""
    res = await client.load_model(spec)
    assert isinstance(res, LoadModuleErr)
    assert "No module name found in source" in res.msg


async def test_loading_model_on_client_without_connection_raises() -> None:
    client = ChaiTransExplorer()
    with pytest.raises(RpcCallWithoutConnection):
        await client.load_model("")
