"""The base class for clients that interact with Apalache's Shai server"""

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
from abc import ABC, abstractclassmethod, abstractmethod
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar, Union

# TODO remove `type: ignore` when stubs are available for grpc.aio See
# https://github.com/shabbyrobe/grpc-stubs/issues/22
import grpc.aio as aio  # type: ignore
from grpc import ChannelConnectivity
from typing_extensions import Self

#############
# DATATYPES #
#############

T = TypeVar("T")


class Source(str):
    """
    A source from which the client can load data,
    """

    # Supported inputs to derive a `Source`
    Input = Union[str, Path]

    def __new__(cls, source: Input):
        if isinstance(source, str):
            return super().__new__(cls, source)
        elif isinstance(source, Path):
            return super().__new__(cls, source.read_text())
        else:
            raise ValueError(
                "Source can only be construced from a str or a Path,"
                f"given {type(source)}"
            )


@dataclass
class RpcErr(ABC):
    """The abstract base class of application errors returned from an RPC call

    Attributes:
        msg: A message explaining the error.
    """

    msg: str


# An RpcResult[T] is a value of type `T` if the RPC succeeded, returning a `T`
# from the server, or else it is an `RpcErr`.
RpcResult = Union[T, RpcErr]


class ChaiException(Exception):
    """The base class of exceptions raised by Chai"""


class RpcCallWithoutConnection(ChaiException):
    """
    Raised when an RPC is called without the client having first obtained a
    connection
    """


class NoServerConnection(ChaiException):
    """Raised if client cannot connect to server after timeout expires"""


# For the type annotation of decorators, see
# https://github.com/microsoft/pyright/blob/main/docs/typed-libraries.md#annotating-decorators
def _requires_connection(rpc_call):
    """
    A decorator to enforce the contract that RPC calls presuppose the
    client has a connection.

    Example usage:

    ```
    @_required_connection
    def rpc_foo(self, ...):
        # ...
    ```
    """

    def checked_rpc_call(client, *args, **kwargs):
        if not client.is_connected():
            raise RpcCallWithoutConnection(f"calling method {rpc_call.__name__}")
        else:
            # This is a method invocation on `client`, just using prefix notation
            return rpc_call(client, *args, **kwargs)

    return checked_rpc_call


# The type of the grcp service accessed by the client
Service = TypeVar("Service")


class Chai(Generic[Service], Awaitable, ABC):
    """Chai: Client for Human-Apalache Interaction

    This is the base class implementing core functionality required to connect
    to Shai: Server for Human-Apalache Interaction. Specific functionality
    provided by the server's services is exposed through service-specific
    subclasses.

    This class implements the contextmanager protocol, and is meant to be used
    in a `with` statement to ensure that resources are cleaned up.

    Example usage:

    ```
    from client import Chai

    with Chai.create() as client:
        assert client.is_connected()
        # Do stuff
    ```

    The client will be closed automatically, and its connection terminated when
    leaving the context.

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

    _DEFAULT_DOMAIN = "localhost"
    _DEFAULT_PORT = 8822
    _DEFAULT_TIMEOUT = 60.0

    @abstractclassmethod
    def _service(cls, channel: aio.Channel) -> Service:
        """Constructor for the protobuf derived service stub"""
        ...

    # TODO(shonfeder): Ideally there would be a single shared ping request
    # but the grpc generation tooling for python behaves very poorly w/r/t
    # module paths and grpc packages: https://github.com/grpc/grpc/issues/9575
    # Simply duplicating the message in each service is the most simple hack
    # to workaround these problems I'm currently aware of.
    @classmethod
    @property
    @abstractmethod
    def PING_REQUEST(cls) -> Any:
        """The PingRequest message belonging to the service"""
        ...

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

        domain = domain or self._DEFAULT_DOMAIN
        port = port or self._DEFAULT_PORT
        timeout = timeout or self._DEFAULT_TIMEOUT

        self._channel_spec = f"{domain}:{port}"
        self._timeout = timeout
        self._channel: Optional[aio.Channel] = None

        # Used to store the gRPC service stub provoding the lower-level gRPC
        # functionality
        self._stub: Service

    # We need the client to implement the await protocol for our async
    # contextmanager `create`
    def __await__(self):
        async def closure():
            return self

        return closure().__await__()

    # The `create` class method lets us use grpcio.aio's async context manager
    # to safely manage the state of the channel, and provide the user with an
    # instance of the Chai client in that context.
    @classmethod
    @asynccontextmanager
    async def create(cls, *args: Any, **kwargs: Any) -> AsyncIterator[Self]:
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

    async def connect(self, channel: Optional[aio.Channel] = None) -> Chai[Service]:
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

        self._stub = self._service(self._channel)

        # Set up a timer so we can timeout if no connection is obtained in time
        loop = asyncio.get_running_loop()
        end_time = loop.time() + self._timeout
        while loop.time() < end_time:
            try:
                await self._stub.ping(self.PING_REQUEST)  # type: ignore
                return self
            except aio.AioRpcError:
                # We weren't able to establish a connection this try
                continue
        else:
            raise NoServerConnection(f"after {self._timeout} seconds")

    def is_connected(self) -> bool:
        """True if the client has an open connection on a ready channel"""
        return (
            self._channel is not None
            and self._channel.get_state() is ChannelConnectivity.READY
        )

    async def close(self) -> None:
        """Close the client, cleaning up connections and channels"""
        if (
            self._channel is not None
            and self._channel.get_state() is not ChannelConnectivity.SHUTDOWN
        ):
            await self._channel.close()
