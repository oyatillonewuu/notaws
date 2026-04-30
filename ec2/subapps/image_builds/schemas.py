from dataclasses import dataclass

from ec2.subapps.image_builds.enums import Status

from .models import ImageBuild


@dataclass
class GenericServiceFunctionResult:
    input_build: ImageBuild
    new_build: ImageBuild | None = None
    message: str | None = None
    status: Status = Status.success


class BuildResult(GenericServiceFunctionResult):
    pass


class HandleDockerfileCodeUpdateResult(GenericServiceFunctionResult):
    pass


class TryReplicationResult(GenericServiceFunctionResult):
    pass
