from __future__ import annotations

from collections.abc import Iterator

import pytest
import socket

from subprocess import PIPE, Popen

from chai import Chai


# Utility function
def ping_server(server: str, port: int, timeout: int = 3) -> bool:
    """Ping a server

    Taken from https://stackoverflow.com/a/67217558/1187277
    """
    try:
        socket.setdefaulttimeout(timeout)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((server, port))
    except OSError:
        return False
    else:
        s.close()
        return True


# Fixture to start and clean up Apalache's Shai server
#
# - `autouse=True`:
#
#   Ensures that the fixutre is provided (i.e., that the server is started)
#   for every test.
#
# - `scope="module"`:
#
#   Specifies that this fixture is created once for every test in the module,
#   rather than created over and over See
#   https://docs.pytest.org/en/6.2.x/fixture.html#scope-sharing-fixtures-across-classes-modules-packages-or-session
@pytest.fixture(autouse=True, scope="module")
def server() -> Iterator[Popen]:
    # TODO Pass port to server explicitly when that is supported
    process = Popen(["apalache-mc", "server"], stdout=PIPE)
    if process.stdout is None:
        raise RuntimeError(
            "No output from Apalache server, cannot confirm it's running"
        )
    for line in process.stdout:
        if "The Apalache server is running." in line.decode("UTF-8"):
            break
    # Startup can take quite some time, especially on the CI machines
    timeout_secs = 60
    if not ping_server(Chai.DEFAULT_DOMAIN, Chai.DEFAULT_PORT, timeout_secs):
        raise RuntimeError(
            f"Apalache server did not start after {timeout_secs} seconds"
        )
    yield process
    process.terminate()


# Fixture to provide and clean up a connected client for each test
#
# NOTE: In contrast to the `shai` fixture, we do want to create this once for each test
@pytest.fixture
def client(server: Popen) -> Iterator[Chai]:
    # We need to ensure the server is created before we create the client
    _ = server
    with Chai() as client:
        yield client


def test_can_obtain_a_connection(client: Chai) -> None:
    assert client.isConnected()
