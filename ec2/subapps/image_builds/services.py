from typing import Any

from .enums import ResultStatus
from .exceptions import BuildInUseError
from .models import ImageBuild
from .schemas import (
    BuildResult,
    DeleteResult,
    UnbuildResult,
    UpdateResult,
)
from .tasks import (
    dispatch_build,
    dispatch_image_remove,
    dispatch_replication,
)
from .utils import (
    freeze_operation_on_deprecated,
    is_referenced,
)


@freeze_operation_on_deprecated()
def build(*, current_build: ImageBuild) -> BuildResult:
    result = BuildResult()
    result.status = ResultStatus.warning

    if not current_build.is_built:
        dispatch_build.delay(build_id=current_build.pk)
        result.message = "Build queued."
        return result

    dispatch_replication.delay(
        current_build_id=current_build.pk, dockerfile_code=current_build.dockerfile_code
    )

    result.message = "Rebuild queued."

    return result


@freeze_operation_on_deprecated()
def handle_direct_updates(
    *, current_build: ImageBuild, tag: str | None
) -> UpdateResult:
    result = UpdateResult()

    updates: dict[str, Any] = {k: v for k, v in {"tag": tag}.items() if v is not None}

    for field, value in updates.items():
        setattr(current_build, field, value)

    if updates:
        current_build.save()

    result.message = "Successfully updated."

    return result


@freeze_operation_on_deprecated()
def handle_dockerfile_code_update(
    *, current_build: ImageBuild, dockerfile_code: str
) -> UpdateResult:
    dockerfile_code_same: bool = current_build.dockerfile_code == dockerfile_code

    result = UpdateResult()
    result.status = ResultStatus.warning

    if dockerfile_code_same:
        result.message = "No update. Dockerfile code is same."
        return result

    if not current_build.is_built:
        current_build.update({"dockerfile_code": dockerfile_code})
        result.message = "Update successful."
        result.status = ResultStatus.success
        return result

    dispatch_replication.delay(
        current_build_id=current_build.pk, dockerfile_code=dockerfile_code
    )
    result.message = "Replication queued."

    return result


@freeze_operation_on_deprecated()
def unbuild(*, current_build: ImageBuild) -> UnbuildResult:
    result = UnbuildResult()
    result.status = ResultStatus.warning

    if is_referenced(current_build):
        raise BuildInUseError("Build is referenced by an Instance or Image")

    if current_build.is_built:
        dispatch_image_remove.delay(image_id=current_build.docker_image_id)
        current_build.update({"docker_image_id": None})
        result.message = "Image removal queued. Image id set to None."
    else:
        result.status = ResultStatus.error
        result.message = "Cannot unbuild. The image is not built."

    return result


def delete_build(*, current_build: ImageBuild) -> DeleteResult:
    result = DeleteResult()
    result.status = ResultStatus.warning
    result.message = ""

    if is_referenced(current_build):
        raise BuildInUseError("Build is referenced by an Instance or Image")

    if current_build.is_built:
        dispatch_image_remove.delay(image_id=current_build.docker_image_id)
        result.message = "Image removal queued. "

    current_build.delete()
    result.message += "DB record deleted."

    return result


# TODO: implement actual job.
