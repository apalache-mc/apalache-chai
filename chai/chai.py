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
from typing_extensions import Concatenate, ParamSpec

import chai.transExplorer_pb2 as msg
import chai.transExplorer_pb2_grpc as service

T = TypeVar("T")
# See https://peps.python.org/pep-0612
P = ParamSpec("P")


@dataclass
class RpcErr:
    """The base type of application errors returned from an RPC call"""

    msg: str


class LoadModuleErr(RpcErr):
    """Represents an error when loading a module (e.g., a parse error)"""


# An RpcResult[T] is a value of type `T` if the RPC succeeded, returning a `T`
# from the server, or else it is an `RpcErr`.
RpcResult = Union[T, RpcErr]

# A `Source` is one of the data types from which the client supports loading
# data.
Source = Union[str, Path]


def _content_of_source(source: Source) -> str:
    if isinstance(source, str):
        return source
    elif isinstance(source, Path):
        return source.read_text()


class ChaiException(Exception):
    """The base class of exceptions raised by Chai"""


class NoServerConnection(ChaiException):
    """Raised if client cannot connect to server after timeout expires"""


class RpcCallWithoutConnection(ChaiException):
    """
    Raised when an RPC is called without the client having first obtained a
    connection
    """


def _requires_connection(rpc_call: RpcMethod[P, T]) -> RpcMethod[P, T]:
    """
    Decorator to enforce the contract that RPC calls presuppose the
    client has a connection
    """

    def checked_rpc_call(client: Chai, *args: P.args, **kwargs: P.kwargs) -> Any:
        if not client.is_connected():
            raise RpcCallWithoutConnection(f"calling method {rpc_call.__name__}")
        else:
            # This is a method invocation on `client`, just using prefix notation
            return rpc_call(client, *args, **kwargs)

    return checked_rpc_call


class Chai(Awaitable):
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

    DEFAULT_DOMAIN = "localhost"
    DEFAULT_PORT = 8822

    # The `create` class method lets us use grpcio.aio's async context manager
    # to safely manage the state of the channel, and provide the user with an
    # instance of the Chai client in that context.
    @classmethod
    @asynccontextmanager
    async def create(cls, *args: Any, **kwargs: Any) -> AsyncIterator[Chai]:
        """Async context manager to create a Chai client with managed resources

        This is the recommended way to create a client, as it ensures that the
        connections and any other resources are cleaned up on exit.

        Example usage:

        ```
        async with Chai.create() as client:
            # interact with the server
        ```
        """
        client = cls(*args, **kwargs)
        try:
            async with aio.insecure_channel(client._channel_spec) as channel:
                await client.connect(channel)
                yield client
        finally:
            # To ensure any resources besides the channel are also cleaned up
            await client.close()

    def __init__(
        self,
        domain: str = DEFAULT_DOMAIN,
        port: int = DEFAULT_PORT,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the Chai client.

        Args:

            domain: domain name or IP where the Apalache server is running
            port: port to which the Apalache server is connected
            timeout: how long to wait before giving up when trying to connect to
                the server (default: 60 seconds)
        """
        self._channel_spec = f"{domain}:{port}"

        self._timeout = timeout

        self._channel: Optional[aio.Channel] = None
        self._conn: Optional[msg.Connection] = None
        self._stub: service.TransExplorerStub

    # We need the client to implement the await protocol
    def __await__(self):
        async def closure():
            return self

        return closure().__await__()

    async def connect(self, channel: Optional[aio.Channel] = None) -> Chai:
        """Obtain a connection from the server

        All other methods assume a connection has been obtained. This method is
        called automatically when the class is used as a context manager.

        If you call this method directly, you should be sure to call
        `self.close()` to ensure the connection and channel is
        """
        if channel is None:
            # No channel is provided, so we create an unmanaged channel,
            # which the caller must close via `self.close()`
            self._channel = aio.insecure_channel(self._channel_spec)
        else:
            # We assume the caller is managing the channel (i.e., via a `with`
            # statement)
            self._channel = channel

        self._stub = service.TransExplorerStub(self._channel)

        req = msg.ConnectRequest()

        # Set up a timer so we can timeout if no connection is obtained in time
        loop = asyncio.get_running_loop()
        end_time = loop.time() + self._timeout
        while loop.time() < end_time:
            try:
                self._conn = await self._stub.OpenConnection(req)  # type: ignore
                return self
            except aio.AioRpcError:
                # We weren't able to establish a connection this try
                continue
        else:
            raise NoServerConnection(f"after {self._timeout} seconds")

    def is_connected(self) -> bool:
        """True if the client has an open connection on a ready channel"""
        return (
            self._conn is not None
            and self._channel is not None
            and self._channel.get_state() is ChannelConnectivity.READY
        )

    @_requires_connection
    async def load_model(
        self,
        spec: Source,
        aux: Optional[Iterable[Source]] = None,
    ) -> RpcResult[dict]:
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
                spec=_content_of_source(spec),
                aux=(_content_of_source(s) for s in aux_sources),
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
RpcMethod = Callable[Concatenate[Chai, P], Awaitable[RpcResult[T]]]
