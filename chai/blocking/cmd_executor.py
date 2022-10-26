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


class ChaiCmdExecutor:
    """A blocking alternative for the async :class:`~chai.ChaiCmdExecutor`

    See the async interface for documentation on the available methods.
    """

    def __init__(
        self,
        domain: Optional[str] = None,
        port: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self._async = chai.ChaiCmdExecutor(domain, port, timeout)

    @classmethod
    @contextmanager
    def create(cls, *args: Any, **kwargs: Any) -> Iterator[Self]:
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
        return self._async.is_connected()

    @make_blocking
    async def check(
        self, input: Source, config: Optional[dict] = None
    ) -> CmdExecutorResult[CmdExecutorCheckError]:
        return await self._async.check(input, config)

    @make_blocking
    async def parse(
        self, input: Source, config: Optional[dict] = None
    ) -> CmdExecutorResult[CmdExecutorParseError]:
        return await self._async.parse(input, config)

    @make_blocking
    async def typecheck(
        self, input: Source, config: Optional[dict] = None
    ) -> CmdExecutorResult[CmdExecutorTypecheckError]:
        return await self._async.typecheck(input, config)
