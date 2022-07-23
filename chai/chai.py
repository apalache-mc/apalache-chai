"""The gRPC client to interact with Apalache's Shai server"""

# Postpone evaluation of annotations
# see:
#  - https://stackoverflow.com/a/33533514/1187277
#  - https://peps.python.org/pep-0563/
#
from __future__ import annotations

from types import TracebackType
from typing import Optional, Type, TypeVar
import grpc
import chai.transExplorer_pb2 as msg
import chai.transExplorer_pb2_grpc as service

T = TypeVar("T")


class Chai:
    """Client for Human-Apalache Interaction

    This class implements the contextmanager protocol, and is meant to be used in
    a `with` statement to ensure that resources are cleaned up.

    Example usage:

    ```
    import chai

    with chai.Chai() as client:
        # TODO: Add key method invocations
        pass
    ```

    If you need to use the class outside of a `with` statement, be sure to
    obtain a connection before doing your work and to close the client when done:

    ```
    try:
      client = chai.Chai().connect()
      # Do stuff
    finally:
      client.close()
    ```

    All methods aside from `connect` assume a connection has been obtained.
    # TODO: document the kind of error raised when the contract is broken
    """

    DEFAULT_DOMAIN = "127.0.0.1"
    DEFAULT_PORT = 8822

    def __init__(self, ip: str = DEFAULT_DOMAIN, port: int = DEFAULT_PORT) -> None:
        self._channel = grpc.insecure_channel(f"{ip}:{port}")
        self._conn: Optional[msg.Connection] = None
        try:
            self._stub = service.TransExplorerStub(self._channel)
        except Exception as e:
            self.close()
            raise e

    def __enter__(self) -> Chai:
        return self.connect()

    def __exit__(self, type: Type[T], value: T, traceback: TracebackType) -> None:
        # Unused variables
        _ = (type, value, traceback)
        self.close()

    def connect(self) -> Chai:
        """Obtain a connection from the server

        All other methods assume a connection has been obtained. This method is
        called automatically when the class is used as a context manager.
        """
        self._conn: Optional[msg.Connection] = self._stub.OpenConnection(
            msg.ConnectRequest()
        )
        return self

    def isConnected(self) -> bool:
        """True if the client has an open connection"""
        return self._conn is not None

    def close(self) -> None:
        """Close the client, cleaning up connections and channels"""
        # TODO: Send RPC to terminate connection (just a courtesy for the server)
        self._channel.close()
