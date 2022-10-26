"""Shared fixutres for all tests

See https://pytest.org/en/latest/reference/fixtures.html#conftest-py-sharing-fixtures-across-multiple-files # noqa: E501
"""
from __future__ import annotations

from collections.abc import Iterator
from subprocess import Popen
from pathlib import Path
import os

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
    this_dir = Path(os.path.dirname(os.path.realpath(__file__)))
    apalache_dir = this_dir / ".." / "apalache"
    # We run apalche in its nix flake to ensure all dependencies are set to the
    # right version. Without this guard, different CI environments may use different
    # java versions when running apalache.
    # See https://github.com/informalsystems/apalache-chai/issues/24
    # TODO Pass port to server explicitly when that is supported
    process = Popen(["nix", "develop", "-c", "apalache-mc", "server"], cwd=apalache_dir)
    yield process
    process.terminate()
