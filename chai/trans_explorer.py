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

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TypeVar, Union

# TODO remove `type: ignore` when stubs are available for grpc.aio See
# https://github.com/shabbyrobe/grpc-stubs/issues/22
import grpc.aio as aio  # type: ignore
from grpc import ChannelConnectivity

import chai.transExplorer_pb2 as msg
import chai.transExplorer_pb2_grpc as service
import chai.client as client

T = TypeVar("T")


class LoadModuleErr(client.RpcErr):
    """Represents an error when loading a module (e.g., a parse error)"""


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

    @classmethod
    def service(cls, channel: aio.Channel) -> service.TransExplorerStub:
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
        self._conn: Optional[msg.Connection] = None
        self._stub: service.TransExplorerStub

    # async def connect(self, channel: Optional[aio.Channel] = None) -> client.Chai:
    #     """Obtain a connection from the server

    #     All other methods assume a connection has been obtained. This method is
    #     called automatically when the class is used as a context manager.

    #     If you call this method directly, you should be sure to call
    #     `self.close()` to ensure the connection and channel is
    #     """
    #     if channel is None:
    #         # No channel is provided, so we create an unmanaged channel,
    #         # which the caller must close via `self.close()`
    #         self._channel = aio.insecure_channel(self._channel_spec)
    #     else:
    #         # We assume the caller is managing the channel (i.e., via a `with`
    #         # statement)
    #         self._channel = channel

    #     self._stub = service.TransExplorerStub(self._channel)

    #     req = msg.ConnectRequest()

    #     # Set up a timer so we can timeout if no connection is obtained in time
    #     loop = asyncio.get_running_loop()
    #     end_time = loop.time() + self._timeout
    #     while loop.time() < end_time:
    #         try:
    #             self._conn = await self._stub.OpenConnection(req)  # type: ignore
    #             return self
    #         except aio.AioRpcError:
    #             # We weren't able to establish a connection this try
    #             continue
    #     else:
    #         raise client.NoServerConnection(f"after {self._timeout} seconds")

    # XXX All but conn part
    def is_connected(self) -> bool:
        """True if the client has an open connection on a ready channel"""
        return (
            self._conn is not None
            and self._channel is not None
            and self._channel.get_state() is ChannelConnectivity.READY
        )

    @client._requires_connection
    async def load_model(
        self,
        spec: client.Source.Input,
        aux: Optional[Iterable[client.Source]] = None,
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

        resp: msg.LoadModelResponse = await self._stub.LoadModel(
            msg.LoadModelRequest(
                conn=self._conn,
                spec=client.Source(spec),
                aux=(client.Source(s) for s in aux_sources),
            )
        )  # type: ignore

        if resp.HasField("err"):
            return LoadModuleErr(resp.err)
        else:
            return json.loads(resp.spec)

    async def close(self) -> None:
        """Close the client, cleaning up connections and channels"""
        if (
            self._channel is not None
            and self._channel.get_state() is not ChannelConnectivity.SHUTDOWN
        ):
            await self._channel.close()
        # TODO: Send RPC to terminate connection (just a courtesy for the server)


# An `RpcMethod[P, T]` is an instance method of the `Chai` client, with any
# paramters, `P`, and returning a value of type `RpcResult[T]`.
#
# For info on the typing mechanim here, see https://peps.python.org/pep-0612/
#
# NOTE: Must follow the definition of `Chai` in order to have that class in
# scope.
# RpcMethod = Callable[Concatenate[Chai, P], Awaitable[client.RpcResult[T]]]
