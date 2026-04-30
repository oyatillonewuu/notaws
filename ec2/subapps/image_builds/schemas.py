from dataclasses import dataclass

from .enums import ResultStatus
from .models import ImageBuild


@dataclass
class GenericServiceFunctionResult:
    message: str | None = None
    status: ResultStatus = ResultStatus.success


class BuildResult(GenericServiceFunctionResult):
    pass


class UpdateResult(GenericServiceFunctionResult):
    pass


class UnbuildResult(GenericServiceFunctionResult):
    pass


class DeleteResult(GenericServiceFunctionResult):
    pass


@dataclass
class TryReplicationResult:
    input_build: ImageBuild
    new_build: ImageBuild | None = None
    message: str | None = None
    status: ResultStatus = ResultStatus.success
