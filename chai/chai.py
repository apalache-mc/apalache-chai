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
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Any, Optional, TypeVar

# TODO remove `type: ignore` when stubs are available for grpc.aio See
# https://github.com/shabbyrobe/grpc-stubs/issues/22
import grpc.aio as aio  # type: ignore
from grpc import ChannelConnectivity

import chai.transExplorer_pb2 as msg
import chai.transExplorer_pb2_grpc as service

T = TypeVar("T")


class NoServerConnection(Exception):
    """Raised if client cannot connect to server after timeout expires"""


class Chai(Awaitable):
    """Client for Human-Apalache Interaction

    This class implements the contextmanager protocol, and is meant to be used in
    a `with` statement to ensure that resources are cleaned up.

    Example usage:

    ```
    from chai import Chai

    with Chai.create() as client:
        assert client.is_connected()
        # TODO: Add key method invocations
    ```

    If you need to use the class outside of a `with` statement, be sure to
    obtain a connection before doing your work and to close the client when done:

    ```
    client = Chai()
    try:
        client.connect()
        # Do more stuff
    finally:
        client.close()
    ```

    All methods aside from `connect` assume a connection has been obtained.
    # TODO: document the kind of error raised when the contract is broken
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
        self._stub: Optional[service.TransExplorerStub] = None
        self._conn: Optional[msg.Connection] = None

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

        # Set up a timer so we can timeout if not connection is obtained in time
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

    async def close(self) -> None:
        """Close the client, cleaning up connections and channels"""
        if (
            self._channel is not None
            and self._channel.get_state() is not ChannelConnectivity.SHUTDOWN
        ):
            await self._channel.close()
        # TODO: Send RPC to terminate connection (just a courtesy for the server)
