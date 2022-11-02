"""The gRPC client to interact with Apalache's Shai server"""

# TODO: Mypy can't currently generate stubs for the grpc.aio code, so we have a
# few `type: ignore` annotations scattered around. Remove these when
# https://github.com/nipunn1313/mypy-protobuf/issues/216 is closed.

# Postpone evaluation of annotations
# see:
#  - https://stackoverflow.com/a/33533514/1187277
#  - https://peps.python.org/pep-0563/
#
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, TypeVar, Union

# TODO remove `type: ignore` when stubs are available for grpc.aio See
# https://github.com/shabbyrobe/grpc-stubs/issues/22
import grpc.aio as aio  # type: ignore

import chai.client as client
import chai.transExplorer_pb2 as msg
import chai.transExplorer_pb2_grpc as service

T = TypeVar("T")


# TODO: remove in favor of `chai.source.Source`
def _load_input(source: Union[str, Path]) -> str:
    """Convert an Input into a string:

    - loading the contents of a file specified by a `Path`
    - acting as identity on a string
    """
    if isinstance(source, str):
        return source
    elif isinstance(source, Path):
        return source.read_text()
    else:
        raise ValueError(
            "Source can only be construced from a str or a Path,"
            f"given {type(source)}"
        )


@dataclass
class LoadModuleErr(client.RpcErr):
    """Represents an error when loading a module (e.g., a parse error)"""

    msg: str


class ChaiTransExplorer(client.Chai[service.TransExplorerStub]):
    """Client for Human-Apalache Interaction

    This class implements the contextmanager protocol, and is meant to be used
    in a `with` statement to ensure that resources are cleaned up.

    Example usage:

    ```
    from chai import Chai

    with Chai.create() as client:
        assert client.is_connected()
        spec_data = client.load_model(Path(.) / 'my' / 'spec.tla')
    ```

    If you need to use the class outside of a `with` statement, be sure to
    obtain a connection before doing your work and to close the client when
    done:

    ```
    client = Chai()
    try:
        client.connect()
        # Do more stuff
    finally:
        client.close()
    ```

    All methods aside from `connect` assume a connection has been obtained.
    Calling an RPC method on the client without first obtaining a connection
    will raise an `RpcCallWithoutConnection` exception.
    """

    _PING_REQUEST = msg.PingRequest()  # type: ignore

    @classmethod
    def _service(cls, channel: aio.Channel) -> service.TransExplorerStub:
        return service.TransExplorerStub(channel)

    def __init__(
        self,
        domain: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """Initialize the Chai client.

        Args:

            domain: domain name or IP where the Apalache server is running
            port: port to which the Apalache server is connected
            timeout: how long to wait before giving up when trying to connect to
                the server (default: 60 seconds)
        """
        super().__init__(domain, port, timeout)

        # A session token used by the server to track the state for this
        # client's requets.  This is required by the TransExplorer service since
        # it is stateful.
        self._conn: Optional[msg.Connection]

    async def connect(self, channel: Optional[aio.Channel] = None) -> client.Chai:
        """Obtain a connection from the server"""
        await super().connect(channel)
        self._conn = await self._stub.openConnection(
            msg.ConnectRequest()
        )  # type: ignore
        return self

    # Since this service is stateful, we need to also ensure we have obtained a
    # session token
    def is_connected(self) -> bool:
        return super().is_connected() and self._conn is not None

    @client.requires_connection
    async def load_model(
        self,
        spec: Union[str, Path],
        aux: Optional[Iterable[Union[str, Path]]] = None,
    ) -> client.RpcResult[dict]:
        """Load a model into the connected session

        Args:

            spec: a `Source` for a TLA+ specification
            aux: an optional iterable of auxiliary TLA+ modules

        Returns:

            RpcResult[dict]: where dict is the content of the parsed model as a
                dictionary representing ther Apalache IR if successful, or a
                `LoadModuleErr` if something something goes wrong.
        """
        aux_sources = aux or []

        resp: msg.LoadModelResponse = await self._stub.loadModel(
            msg.LoadModelRequest(
                conn=self._conn,
                spec=_load_input(spec),
                aux=(_load_input(s) for s in aux_sources),
            )
        )  # type: ignore

        if resp.HasField("err"):
            err: msg.TransExplorerError = resp.err
            return LoadModuleErr(err.data)
        else:
            return json.loads(resp.spec)


# TODO: Send RPC to terminate connection (just a courtesy for the server)
