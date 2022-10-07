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
    """For unexpected errors"""


def _ensure_is_pass_error(d: dict) -> None:
    if d["error_type"] != "pass_failure":
        raise UnexpectedErrorException(f"Unexpected error receieved from RPC call: {d}")


@dataclass
class CmdExecutorError(ABC):
    pass_name: str

    @abstractclassmethod
    def of_dict(cls, _: dict) -> Self:
        ...


@dataclass
class ParsingError(CmdExecutorError):
    data: List[Tuple[str, str]]  # location, msg errors

    @classmethod
    def of_dict(cls, d: dict) -> ParsingError:
        _ensure_is_pass_error(d)

        data = d["data"]
        pass_name = data["pass_name"]
        if pass_name == "BoundedChecker":
            return ParsingError(pass_name, data)
        else:
            raise UnexpectedErrorException(
                f"Unexpected error receieved from RPC call: {d}"
            )


@dataclass
class TypecheckingError(CmdExecutorError):
    errors: List[Tuple[str, str]]  # location, msg errors

    @classmethod
    def of_dict(cls, d: dict) -> ParsingError | TypecheckingError:
        _ensure_is_pass_error(d)

        data = d["data"]
        pass_name = data["pass_name"]
        if pass_name == "BoundedChecker":
            return TypecheckingError(pass_name, data)
        else:

            return ParsingError.of_dict(d)


@dataclass
class CheckingError(CmdExecutorError):
    checking_result: str
    counter_example: List[Counterexample]

    @classmethod
    def of_dict(cls, d: dict) -> ParsingError | TypecheckingError | CheckingError:
        _ensure_is_pass_error(d)

        data = d["data"]
        pass_name = data["pass_name"]
        if pass_name == "BoundedChecker":
            checking_result = data["error_data"]["checking_result"]
            if checking_result == "Deadlock":
                # TODO We should use the same key for both counterexamples
                counter_examples = data["error_data"]["counterexample"]
            else:
                counter_examples = data["error_data"]["counterexamples"]
            return CheckingError(pass_name, checking_result, counter_examples)
        else:
            return TypecheckingError.of_dict(d)


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
        resp: msg.CmdResponse = await self._stub.run(
            msg.CmdRequest(cmd=msg.Cmd.CHECK, config=_config_json(spec, aux, config))
        )  # type: ignore
        if resp.HasField("failure"):
            return CheckingError.of_dict(json.loads(resp.failure))
        else:
            return json.loads(resp.success)

    async def parse(
        self, module: str, aux: List[str], config: dict
    ) -> RpcResult[CmdExecutorResult[ParsingError]]:
        ...

    async def typecheck(
        self, module: str, aux: List[str], config: dict
    ) -> RpcResult[CmdExecutorResult[ParsingError]]:
        ...
