from dataclasses import dataclass

from .enums import ResultStatus


@dataclass
class GenericServiceFunctionResult:
    message: str | None = None
    status: ResultStatus = ResultStatus.success


@dataclass
class CreateResult(GenericServiceFunctionResult):
    instance_pk: int | None = None


class UpdateResult(GenericServiceFunctionResult):
    pass


class StartResult(GenericServiceFunctionResult):
    pass


class StopResult(GenericServiceFunctionResult):
    pass


class DeleteResult(GenericServiceFunctionResult):
    pass
