"""The gRPC client to interact with the CmdExeuctor service provided by
   Apalache's Shai server"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple, TypeVar, Union

# TODO remove `type: ignore` when stubs are available for grpc.aio See
# https://github.com/shabbyrobe/grpc-stubs/issues/22
import grpc.aio as aio  # type: ignore

import chai.client as client
import chai.cmdExecutor_pb2 as msg
import chai.cmdExecutor_pb2_grpc as service
from chai.source import Source

# Derived from JSON encodings
Counterexample = dict
# A dictionary derived from the apalache ITF format
TlaModule = dict


class UnexpectedErrorException(Exception):
    """For unexpected application errors"""


@dataclass
class CmdExecutorError(client.RpcErr):
    """Base class for known application errors from the CmdExecutor service"""

    pass_name: str
    """The name of the processing pass that produced the error."""


@dataclass
class ParsingError(CmdExecutorError):
    """Records a parsing error"""

    # Set the `msg` field, but don't expose it as settable field in the constructor
    msg: str = field(default="Encountered a parsing error", init=False)
    errors: List[str]
    """A list of parsing error messages."""


@dataclass
class TypecheckingError(CmdExecutorError):
    """Records a typechecking error"""

    # Set the `msg` field, but don't expose it as settable field in the constructor
    msg: str = field(default="Encountered a typechecking error", init=False)
    errors: List[Tuple[str, str]]  # location, msg errors
    """A list of tuples pairing source locations with type error messages."""


@dataclass
class CheckingError(CmdExecutorError):
    """Records a model checking error"""

    # Set the `msg` field, but don't expose it as settable field in the constructor
    msg: str = field(default="Encountered a model checking error", init=False)

    checking_result: str
    """The kind of model checking result. The possible result

    Kinds are as follows

    - Error: A checking violation is found.
    - Deadlock: A deadlock was found.
    - RuntimeError: A runtime error was encountered, preventing checking.
    """

    counter_example: List[Counterexample]
    """A list of counterexamples found

    Each counterexample is a dictionary decoded from the
    Apalache [ITF format](https://apalache.informal.systems/docs/adr/015adr-trace.html?highlight=ITF#the-itf-format).
    """  # noqa: E501


def _check_for_unexpected_err(err: msg.CmdError):
    if err.errorType == msg.UNEXPECTED:
        err_msg = json.loads(err.data)["msg"]
        raise UnexpectedErrorException(
            f"Unexpected error receieved from RPC call: {err_msg}"
        )


Err = TypeVar("Err")

CmdExecutorResult = Union[Err, TlaModule]
"""
Results returned by `ChaiCmdExecutor` methods, parameterized on `Err`,
the application errors they can return
"""

CmdExecutorParseError = ParsingError
"""The application errors that can be returned by the `parse` method"""


CmdExecutorTypecheckError = Union[TypecheckingError, CmdExecutorParseError]
"""The application errors that can be returned by the `typecheck` method"""

CmdExecutorCheckError = Union[CheckingError, CmdExecutorTypecheckError]
"""The application errors that can be returned by the `check` method"""


def _parse_err(data: dict) -> CmdExecutorParseError:
    pass_name = data["pass_name"]
    if pass_name == "SanyParser":
        return ParsingError(pass_name, data["error_data"])
    else:
        raise UnexpectedErrorException(
            f"Unexpected error receieved from RPC call: {data['msg']}"
        )


def _typechecking_err(data: dict) -> CmdExecutorTypecheckError:
    pass_name = data["pass_name"]
    if pass_name == "TypeCheckerSnowcat":
        return TypecheckingError(pass_name, data["error_data"])
    else:
        return _parse_err(data)


def _checking_err(data: dict) -> CmdExecutorCheckError:
    pass_name = data["pass_name"]
    if pass_name == "BoundedChecker":
        error_data = data["error_data"]
        checking_result = error_data["checking_result"]
        if checking_result == "Deadlock":
            # TODO We should use the same key for both counterexamples
            counter_examples = error_data["counterexamples"]
        else:
            counter_examples = error_data["counterexamples"]
        # TODO Handle all other checking errors
        return CheckingError(pass_name, checking_result, counter_examples)
    else:
        return _typechecking_err(data)


class ChaiCmdExecutor(client.Chai[service.CmdExecutorStub]):
    r"""Client for Shai's `CmdExecutor` service

    The `CmdExecutor` service is a stateless service exposing the functionality
    of Apalache's CLI.

    This functionality is exposed through 3 methods, each of which takes 2 arguments:

    - a `chai.source.Source` with the input specification
    - a dictionary [configuring Apalache's
      parameters](https://apalache.informal.systems/docs/apalache/config.html)

    Each method either returns an error (a subclass of `CmdExecutorError`)
    describing the kind of failure and providing useful error data (if
    available), or else a dictionary representing the specification through the
    [JSON encoding](https://apalache.informal.systems/docs/adr/005adr-json.html)
    of  Apalache's TlaIR (TLA Intermediate Representation)

    Example usage:

    ```python
    from chai import ChaiCmdExecutor, Source, CheckingError

    async with ChaiCmdExecutor.create() as client:
        assert client.is_connected()
        spec = '''
            ---- MODULE M ----
            VARIABLES
                \* @type: Bool;
                x,
                \* @type: Bool;
                y

            Init == x = TRUE /\ y = TRUE
            Next == x' = FALSE /\ y' = y
            Inv == x
            ====
            '''
        source = chai.Source(spec)
        res = await client.check(source, config={"checker": {"inv": ["Inv"]}})
        if isinstance(res, CheckingError):
            assert res.checking_result == "Error"
            states = res.counter_example[0]["states"][1]
            assert states == {"#meta": {"index": 1}, "x": False, "y": True}
        elif isinstance(res, ParsingError):
            print("Failed during parsing")
        elif isinstance(res, TypecheckingError):
            print("Failed during typechecking")
        else:
            print("Model checked!")
    ```

    See the documetation of `chai.client.Chai` for instruction on using
    the client safely without a context manager.
    """

    _PING_REQUEST = msg.PingRequest  # type: ignore

    @classmethod
    def _service(cls, channel: aio.Channel) -> service.CmdExecutorStub:
        return service.CmdExecutorStub(channel)

    @client.requires_connection
    async def parse(
        self,
        input: Source,
        config: Optional[dict] = None,
    ) -> CmdExecutorResult[CmdExecutorParseError]:
        """Parse a TLA spec

        Args:

        - `input`: A `chai.source.Source`
        - `config`: Application configuration
        """
        return await self._run_rpc_cmd(
            cmd=msg.Cmd.PARSE,
            input=input,
            config=config,
            err_parser=_parse_err,
        )

    @client.requires_connection
    async def typecheck(
        self,
        input: Source,
        config: Optional[dict] = None,
    ) -> CmdExecutorResult[CmdExecutorTypecheckError]:
        """Typecheck a TLA spec

        Args:

        - `input`: A `chai.source.Source`
        - `config`: Application configuration
        """
        return await self._run_rpc_cmd(
            cmd=msg.Cmd.TYPECHECK,
            input=input,
            config=config,
            err_parser=_typechecking_err,
        )

    @client.requires_connection
    async def check(
        self,
        input: Source,
        config: Optional[dict] = None,
    ) -> CmdExecutorResult[CmdExecutorCheckError]:
        """Model check a TLA spec

        Args:

        - `input`: A `chai.source.Source`
        - `config`: Application configuration
        """
        return await self._run_rpc_cmd(
            cmd=msg.Cmd.CHECK,
            input=input,
            config=config,
            err_parser=_checking_err,
        )

    async def _run_rpc_cmd(
        self,
        *,
        cmd: msg._Cmd.ValueType,
        input: Source,
        config: Optional[dict],
        err_parser: Callable[[dict], CmdExecutorResult[Err]],
    ) -> CmdExecutorResult[Err]:
        rpc_args: dict = config or {}
        # Merge the `input` (as a adict) into the `rpc_args`,
        # with the `input` taking precedence
        # See https://datagy.io/python-merge-dictionaries/#Merge_Python_Dictionaries_with_Item_Unpacking # noqa: E501
        merged_args = {**rpc_args, **input.to_dict()}
        rpc_config = json.dumps(merged_args)
        resp: msg.CmdResponse = await self._stub.run(
            msg.CmdRequest(cmd=cmd, config=rpc_config)
        )  # type: ignore
        if resp.HasField("failure"):
            err: msg.CmdError = resp.failure
            _check_for_unexpected_err(err)
            err_data = json.loads(err.data)
            return err_parser(err_data)
        else:
            return json.loads(resp.success)
