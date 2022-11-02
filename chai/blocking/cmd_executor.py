from contextlib import contextmanager
from typing import Any, Iterator, Optional

from typing_extensions import Self

import chai
from chai.blocking.utils import make_blocking
from chai.cmd_executor import (
    CmdExecutorCheckError,
    CmdExecutorParseError,
    CmdExecutorResult,
    CmdExecutorTypecheckError,
)
from chai.source import Source


class ChaiCmdExecutorBlocking:
    """A blocking alternative for the async `chai.cmd_executor.ChaiCmdExecutor`

    See the async interface for documentation on the available methods.
    """

    def __init__(
        self,
        domain: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> None:
        """See `chai.client.Chai.__init__`"""
        self._async = chai.ChaiCmdExecutor(domain, port, timeout)

    @classmethod
    @contextmanager
    def create(cls, *args: Any, **kwargs: Any) -> Iterator[Self]:
        """See `chai.client.Chai.create`"""
        client = cls(*args, **kwargs)

        @make_blocking
        async def connect_client():
            await client._async.connect()

        @make_blocking
        async def close_client():
            await client._async.close()

        try:
            _ = connect_client()
            yield client
        finally:
            _ = close_client()

    def is_connected(self) -> bool:
        """See `chai.client.Chai.is_connected`"""
        return self._async.is_connected()

    @make_blocking
    async def parse(
        self, input: Source, config: Optional[dict] = None
    ) -> CmdExecutorResult[CmdExecutorParseError]:
        """See `chai.cmd_executor.ChaiCmdExecutor.parse`"""
        return await self._async.parse(input, config)

    @make_blocking
    async def typecheck(
        self, input: Source, config: Optional[dict] = None
    ) -> CmdExecutorResult[CmdExecutorTypecheckError]:
        """See `chai.cmd_executor.ChaiCmdExecutor.typecheck`"""
        return await self._async.typecheck(input, config)

    @make_blocking
    async def check(
        self, input: Source, config: Optional[dict] = None
    ) -> CmdExecutorResult[CmdExecutorCheckError]:
        """See `chai.cmd_executor.ChaiCmdExecutor.check`"""
        return await self._async.check(input, config)
