"""The gRPC client to interact with the CmdExeuctor service provided by Apalache's Shai server"""

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

import chai.cmdExecutor_pb2 as msg
import chai.cmdExecutor_pb2_grpc as service
