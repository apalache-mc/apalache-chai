"""The gRPC client to interact with the CmdExeuctor service provided by
   Apalache's Shai server"""
from __future__ import annotations

import json
from abc import ABC, abstractclassmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple, TypeVar

# TODO remove `type: ignore` when stubs are available for grpc.aio See
# https://github.com/shabbyrobe/grpc-stubs/issues/22
import grpc.aio as aio  # type: ignore
from typing_extensions import Self

import chai.client as client
import chai.cmdExecutor_pb2 as msg
import chai.cmdExecutor_pb2_grpc as service
from chai.client import RpcResult

Input = client.Source.Input
# Derived from JSON encodings
Counterexample = dict
TlaModule = dict


class UnexpectedErrorException(Exception):
    """For unexpected application errors"""


@dataclass
class CmdExecutorError(ABC):
    """The base class for known application errors returned by the CmdExecutor service

    Attributes:
        pass_name: The name of the processing pass that produced the error.
    """

    pass_name: str

    # Derive an error from decoded JSON
    @abstractclassmethod
    def _of_dict(cls, _: dict) -> Self:
        ...


def _ensure_is_pass_failure(d: dict) -> None:
    if d["error_type"] != "pass_failure":
        raise UnexpectedErrorException(f"Unexpected error receieved from RPC call: {d}")


@dataclass
class ParsingError(CmdExecutorError):
    """Records a parsing error

    Attributes:
        errors: A list of parsing error messages.
    """

    errors: List[str]

    @classmethod
    def _of_dict(cls, d: dict) -> ParsingError:
        _ensure_is_pass_failure(d)

        data = d["data"]
        pass_name = data["pass_name"]
        if pass_name == "SanyParser":
            return ParsingError(pass_name, data)
        else:
            raise UnexpectedErrorException(
                f"Unexpected error receieved from RPC call: {d}"
            )


@dataclass
class TypecheckingError(CmdExecutorError):
    """Records a typechecking error

    Attributes:
        errors: A list of tuples pairing source locations with type error
            messages.
    """

    errors: List[Tuple[str, str]]  # location, msg errors

    @classmethod
    def _of_dict(cls, d: dict) -> ParsingError | TypecheckingError:
        _ensure_is_pass_failure(d)

        pass_name = d["data"]["pass_name"]
        errors = d["data"]["error_data"]
        if pass_name == "TypeCheckerSnowcat":
            return TypecheckingError(pass_name, errors)
        else:
            return ParsingError._of_dict(d)


@dataclass
class CheckingError(CmdExecutorError):
    """Records a model checking error

    Attributes:
        checking_result: The kind of model checking result. The possible result kinds are
            - Error: A checking violation is found.
            - Deadlock: A deadlock was found.
            - RuntimeError: A runtime error was encountered, preventing checking.
        counter_examples: A list of counterexamples found.
    """

    checking_result: str
    counter_example: List[Counterexample]

    @classmethod
    def _of_dict(cls, d: dict) -> ParsingError | TypecheckingError | CheckingError:
        _ensure_is_pass_failure(d)

        error_data = d["data"]["error_data"]
        pass_name = d["data"]["pass_name"]
        if pass_name == "BoundedChecker":
            checking_result = error_data["checking_result"]
            if checking_result == "Deadlock":
                # TODO We should use the same key for both counterexamples
                counter_examples = error_data["counterexample"]
            else:
                counter_examples = error_data["counterexamples"]
            # TODO Handle all other checking errors
            return CheckingError(pass_name, checking_result, counter_examples)
        else:
            return TypecheckingError._of_dict(d)


E = TypeVar("E")
CmdExecutorResult = RpcResult[E | TlaModule]


def _str_source(spec, aux):
    return {"source": {"type": "string", "content": spec, "aux": aux}}


def _config_json(spec: Input, aux: Optional[List[Input]], cfg: Optional[dict]) -> str:
    # TODO: error if source already set in config?
    aux = aux or []
    config = cfg or {}
    return json.dumps(config | {"input": _str_source(spec, aux)})


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
        spec: client.Source.Input,
        aux: Optional[List[client.Source.Input]] = None,
        config: Optional[dict] = None,
    ) -> CmdExecutorResult[ParsingError | TypecheckingError | CheckingError]:
        """Model check a TLA spec

        Args:
            spec: The root module, as a string or path to a file.
            aux: Auxiliary modules extended by the root module.
            config: Application configuration, as documented in `Apalache's
                Manual <https://apalache.informal.systems/docs/apalache/config.html#configuration-files>`_
        """
        resp: msg.CmdResponse = await self._stub.run(
            msg.CmdRequest(cmd=msg.Cmd.CHECK, config=_config_json(spec, aux, config))
        )  # type: ignore
        if resp.HasField("failure"):
            return CheckingError._of_dict(json.loads(resp.failure))
        else:
            return json.loads(resp.success)

    @client._requires_connection
    async def parse(
        self, module: str, aux: List[str], config: dict
    ) -> RpcResult[CmdExecutorResult[ParsingError]]:
        ...

    @client._requires_connection
    async def typecheck(
        self, module: str, aux: List[str], config: dict
    ) -> RpcResult[CmdExecutorResult[ParsingError]]:
        ...
