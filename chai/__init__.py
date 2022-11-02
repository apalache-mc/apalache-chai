"""
## A Client for Human-Apalache Interaction

Chai is a library that provides transparent access to the functionality of the
[Apalache](https://apalache.informal.systems/) model checker via RPC calls to
Apalache's server. Apalache's server is called "Shai" short for "Client for
Human-Apalache Interaction". Together, Chai and Shai make Apalache's model
checking available from python libraries.

All useful functionality of the library is currently focused on
`chai.cmd_executor.ChaiCmdExecutor` which exposes the CLI functionality of
Apalache.
"""

from chai.client import (
    NoServerConnection,
    RpcCallWithoutConnection,
    RpcErr,
    Chai,
    requires_connection,
)
from chai.cmd_executor import (
    ChaiCmdExecutor,
    CmdExecutorError,
    CheckingError,
    TypecheckingError,
    ParsingError,
)
from chai.source import Source
from chai.blocking.cmd_executor import ChaiCmdExecutorBlocking

# These classes are not currently provided in __all__ because they
# development on them was suspended for the moment, and they are not
# production ready.
from chai.trans_explorer import ChaiTransExplorer, LoadModuleErr

__all__ = [
    "ChaiCmdExecutor",
    "Source",
    "CmdExecutorError",
    "CheckingError",
    "TypecheckingError",
    "ParsingError",
    "RpcErr",
    "RpcCallWithoutConnection",
    "NoServerConnection",
    "Chai",
    "requires_connection",
    "ChaiCmdExecutorBlocking",
]
