from dataclasses import dataclass

from .enums import ResultStatus


@dataclass
class GenericServiceFunctionResult:
    message: str | None = None
    status: ResultStatus = ResultStatus.success


@dataclass
class CreateResult(GenericServiceFunctionResult):
    instance_pk: int | None = None


@dataclass
class UpdateResult(GenericServiceFunctionResult):
    pass


@dataclass
class StartResult(GenericServiceFunctionResult):
    pass


@dataclass
class StopResult(GenericServiceFunctionResult):
    pass


@dataclass
class DeleteResult(GenericServiceFunctionResult):
    pass
