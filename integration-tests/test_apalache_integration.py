from __future__ import annotations

from collections.abc import Iterator

import pytest
import socket
import time

from subprocess import Popen
from chai import Chai


# Utility function
def wait_for_server(server: str, port: int, timeout: int) -> bool:
    """Ping a server

    Adapated from https://stackoverflow.com/a/67217558/1187277
    """
    remaining_time = timeout
    while remaining_time > 0:
        socket.setdefaulttimeout(remaining_time)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((server, port))
        except TimeoutError:
            # We ran out of time waiting for a connection on the socket
            return False
        except OSError:
            # We weren't able to connect to the socket, wait a bit, and try again
            remaining_time -= 1
            time.sleep(1)
        else:
            # We connected!
            s.close()
            return True
    else:
        # We ran out of remaining_time, so give up
        return False


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
    # Startup can take quite some time, especially on the CI machines
    timeout_secs = 60
    if not wait_for_server(Chai.DEFAULT_DOMAIN, Chai.DEFAULT_PORT, timeout_secs):
        raise RuntimeError(
            f"Apalache server did not start after {timeout_secs} seconds"
        )
    yield process
    process.terminate()


# Fixture to provide and clean up a connected client for each test
#
# NOTE: In contrast to the `server` fixture, we do want to create this once for
# each test
@pytest.fixture
def client(server: Popen) -> Iterator[Chai]:
    # We need to ensure the server is created before we create the client
    _ = server
    with Chai() as client:
        yield client


def test_can_obtain_a_connection(client: Chai) -> None:
    assert client.isConnected()
