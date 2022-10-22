"""The gRPC client to interact with the CmdExeuctor service provided by
   Apalache's Shai server"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple, TypeVar, Union

# TODO remove `type: ignore` when stubs are available for grpc.aio See
# https://github.com/shabbyrobe/grpc-stubs/issues/22
import grpc.aio as aio  # type: ignore

import chai.client as client
import chai.cmdExecutor_pb2 as msg
import chai.cmdExecutor_pb2_grpc as service
from chai.source import Source

Input = Source.Input
# Derived from JSON encodings
Counterexample = dict
TlaModule = dict


class UnexpectedErrorException(Exception):
    """For unexpected application errors"""


@dataclass
class CmdExecutorError(client.RpcErr):
    """Base class for known application errors from the CmdExecutor service

    Attributes:
        pass_name: The name of the processing pass that produced the error.
    """

    pass_name: str


@dataclass
class ParsingError(CmdExecutorError):
    """Records a parsing error

    Attributes:
        errors: A list of parsing error messages.
    """

    # Set the `msg` field, but don't expose it as settable field in the constructor
    msg: str = field(default="Encountered a parsing error", init=False)
    errors: List[str]


@dataclass
class TypecheckingError(CmdExecutorError):
    """Records a typechecking error

    Attributes:
        errors: A list of tuples pairing source locations with type error
            messages.
    """

    # Set the `msg` field, but don't expose it as settable field in the constructor
    msg: str = field(default="Encountered a typechecking error", init=False)
    errors: List[Tuple[str, str]]  # location, msg errors


@dataclass
class CheckingError(CmdExecutorError):
    """Records a model checking error

    Attributes:
        checking_result: The kind of model checking result. The possible result
            kinds are as follows

            - Error: A checking violation is found.
            - Deadlock: A deadlock was found.
            - RuntimeError: A runtime error was encountered, preventing checking.
        counter_examples: A list of counterexamples found.
    """

    # Set the `msg` field, but don't expose it as settable field in the constructor
    msg: str = field(default="Encountered a model checking error", init=False)
    checking_result: str
    counter_example: List[Counterexample]


def _check_for_unexpected_err(err: msg.CmdError):
    if err.errorType == msg.UNEXPECTED:
        err_msg = json.loads(err.data)["msg"]
        raise UnexpectedErrorException(
            f"Unexpected error receieved from RPC call: {err_msg}"
        )


Err = TypeVar("Err")

# Results returned by `ChaiCmdExecutor` methods, parameterized on `Err`,
# the application errors they can return
CmdExecutorResult = Union[Err, TlaModule]

# The application errors that can be returned by the `parse` method
CmdExecutorParseError = ParsingError

# The application errors that can be returned by the `typecheck` method
CmdExecutorTypecheckError = TypecheckingError | CmdExecutorParseError

# The application errors that can be returned by the `check` method
CmdExecutorCheckError = CheckingError | CmdExecutorTypecheckError


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


def _config_json(source: Source, cfg: Optional[dict]) -> str:
    # TODO: error if source already set in config?
    config = cfg or {}
    return json.dumps(config | source.to_dict())


class ChaiCmdExecutor(client.Chai[service.CmdExecutorStub]):
    r"""Client for Shai's `CmdExecutor` service

    The `CmdExecutor` service is a stateless service exposing the functionality
    of Apalache's CLI.

    Example usage:

    ```
    from chai import ChaiCmdExecutor

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
        res = await client.check(spec, config={"checker": {"inv": ["Inv"]}})
        assert isinstance(res, CheckingError)
        assert res.checking_result == "Error"
        states = res.counter_example[0]["states"][1]
        assert states == {"#meta": {"index": 1}, "x": False, "y": True}

    See the documetation of :class:`~chai.client.Chai` for instruction on using
    the client safely without a context manager.
    ```
    """

    PING_REQUEST = msg.PingRequest  # type: ignore

    @classmethod
    def _service(cls, channel: aio.Channel) -> service.CmdExecutorStub:
        return service.CmdExecutorStub(channel)

    @client._requires_connection
    async def check(
        self,
        input: Source,
        config: Optional[dict] = None,
    ) -> CmdExecutorResult[CmdExecutorCheckError]:
        """Model check a TLA spec

        Args:
            spec: The root module, as a string or path to a file.
            aux: Auxiliary modules extended by the root module.
            config: Application configuration, as documented in `Apalache's
                Manual <https://apalache.informal.systems/docs/apalache/config.html#configuration-files>`_ # noqa
        """
        return await self._run_rpc_cmd(
            cmd=msg.Cmd.CHECK,
            input=input,
            config=config,
            err_parser=_checking_err,
        )

    @client._requires_connection
    async def parse(
        self,
        input: Source,
        config: Optional[dict] = None,
    ) -> CmdExecutorResult[CmdExecutorParseError]:
        """Parse a TLA spec

        Args:
            spec: The root module, as a string or path to a file.
            aux: Auxiliary modules extended by the root module.
            config: Application configuration, as documented in `Apalache's
                Manual <https://apalache.informal.systems/docs/apalache/config.html#configuration-files>`_ # noqa
        """
        return await self._run_rpc_cmd(
            cmd=msg.Cmd.PARSE,
            input=input,
            config=config,
            err_parser=_parse_err,
        )

    @client._requires_connection
    async def typecheck(
        self,
        input: Source,
        config: Optional[dict] = None,
    ) -> CmdExecutorResult[CmdExecutorTypecheckError]:
        """Typecheck a TLA spec

        Args:
            spec: The root module, as a string or path to a file.
            aux: Auxiliary modules extended by the root module.
            config: Application configuration, as documented in `Apalache's
                Manual <https://apalache.informal.systems/docs/apalache/config.html#configuration-files>`_ # noqa
        """
        return await self._run_rpc_cmd(
            cmd=msg.Cmd.TYPECHECK,
            input=input,
            config=config,
            err_parser=_typechecking_err,
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
        rpc_config = json.dumps(rpc_args | input.to_dict())
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
