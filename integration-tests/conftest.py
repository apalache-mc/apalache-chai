"""Shared fixutres for all tests

See https://pytest.org/en/latest/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files # noqa: E501
"""
from __future__ import annotations

from collections.abc import Iterator
from subprocess import Popen

import pytest


# Fixture to start and clean up Apalache's Shai server
#
# - `autouse=True`:
#
#   Ensures that the fixture is provided (i.e., that the server is started)
#   for every test.
#
# - `scope="session"`:
#
#   Specifies that this fixture is created only once for all the tests in any
#   test session, rather than created once per test. I.e., we only share a
#   single server between all the clients
#
#   tested in all of our test files. See
#   https://docs.pytest.org/en/6.2.x/fixture.html#scope-sharing-fixtures-across-classes-modules-packages-or-session # noqa: E501
@pytest.fixture(autouse=True, scope="session")
def server() -> Iterator[Popen]:
    # TODO Pass port to server explicitly when that is supported
    process = Popen(["apalache-mc", "server"])
    yield process
    process.terminate()
