from __future__ import annotations

from collections.abc import Iterator
from subprocess import Popen

import pytest

from chai.blocking import ChaiCmdExecutorBlocking
from chai.source import Source


# Fixture to provide and clean up a connected client for each test
#
# NOTE: In contrast to the `server` fixture, we do want to create this once for
# each test
@pytest.fixture
def client(server: Popen) -> Iterator[ChaiCmdExecutorBlocking]:
    # We need to ensure the server is created before we create the client
    _ = server
    with ChaiCmdExecutorBlocking.create() as client:
        yield client


def test_can_obtain_a_blocking_connection(client: ChaiCmdExecutorBlocking) -> None:
    assert client.is_connected()


# NOTE: The following tests are just blocking versions of the happypath
# tests in `test_cmd_executor_integration.py`
#
# We do not exercise any of the error-handling functionality, since that is
# already covered in the async tests. Here, we only need to confirm that
# blocking calls can indeed be made.


def test_can_check_blocking_model(client: ChaiCmdExecutorBlocking) -> None:
    spec = """
---- MODULE M ----
Init == TRUE
Next == TRUE
====
"""
    res = client.check(Source(spec))
    assert isinstance(res, dict)
    m = res["modules"][0]
    assert m["name"] == "M" and m["kind"] == "TlaModule"


def test_typechecking_a_well_typed_model_blocking_succeeds(
    client: ChaiCmdExecutorBlocking,
) -> None:
    spec = r"""
---- MODULE M ----
EXTENDS Integers
VARIABLES
    \* @type: Int;
    x

Add1 == x + 1
====
"""
    res = client.typecheck(Source(spec))
    # We get a dictionary back
    assert isinstance(res, dict)
    # And the dictionary is an Apalache IR representation of the module
    assert res["name"] == "ApalacheIR"


def test_parsing_a_valid_model_blocking_succeeds(
    client: ChaiCmdExecutorBlocking,
) -> None:
    spec = r"""
---- MODULE M ----
Foo == TRUE
====
"""
    res = client.parse(Source(spec))
    # We get a dictionary back
    assert isinstance(res, dict)
    # And the dictionary is an Apalache IR representation of the module
    assert res["name"] == "ApalacheIR"
