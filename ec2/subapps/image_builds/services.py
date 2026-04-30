import functools
from copy import deepcopy
from typing import Any

from django.db import transaction

import docker_ops
from docker_ops.utils import text_to_fileobj
from ec2.subapps.image_builds.enums import Status
from ec2.subapps.image_builds.schemas import (
    BuildResult,
    HandleDockerfileCodeUpdateResult,
    TryReplicationResult,
)

from .exceptions import BuildInUseError, CannotOperateOnDeprecatedBuild
from .models import ImageBuild


def freeze_operation_on_deprecated(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        current_build = kwargs.get("current_build")
        if current_build is not None and current_build.deprecated:
            raise CannotOperateOnDeprecatedBuild(
                "Cannot carry this operation. Build is deprecated."
            )
        result = func(*args, **kwargs)

        return result

    return wrapper


@freeze_operation_on_deprecated
def build(*, current_build: ImageBuild) -> BuildResult:
    result = BuildResult(input_build=current_build)

    if not current_build.is_built:
        new_id = build_from(current_build)
        current_build.update({"docker_image_id": new_id})
        result.message = "Successfully built."
        return result

    replication_result: TryReplicationResult = try_replicate_replace_if_image_divergent(  # type: ignore
        current_build=current_build,  # type: ignore
        dockerfile_code=current_build.dockerfile_code,  # type: ignore
    )

    if replication_result.new_build is not None:
        result.new_build = replication_result.new_build
        result.message = replication_result.message
        result.status = replication_result.status
    else:
        result.message = "Did not rebuild. Resulting image same."

    return result


@freeze_operation_on_deprecated
def handle_direct_updates(*, current_build: ImageBuild, tag: str | None) -> None:
    updates: dict[str, Any] = {k: v for k, v in {"tag": tag}.items() if v is not None}

    for field, value in updates.items():
        setattr(current_build, field, value)

    if updates:
        current_build.save()


@freeze_operation_on_deprecated
def handle_dockerfile_code_update(
    *, current_build: ImageBuild, dockerfile_code: str
) -> HandleDockerfileCodeUpdateResult:
    dockerfile_code_same: bool = current_build.dockerfile_code == dockerfile_code

    result = HandleDockerfileCodeUpdateResult(
        input_build=current_build,
    )

    if dockerfile_code_same:
        result.message = "No update. Dockerfile code is same."
        return result

    if not current_build.is_built:
        current_build.update({"dockerfile_code": dockerfile_code})
        result.message = "Update successful."
        return result

    replication_handler_result: TryReplicationResult = (
        try_replicate_replace_if_image_divergent(  # type: ignore
            current_build=current_build,  # type: ignore
            dockerfile_code=dockerfile_code,  # type: ignore
        )
    )
    replication_handler_message: str | None = replication_handler_result.message

    if replication_handler_result.new_build is not None:
        result.new_build = replication_handler_result.new_build
        result.message = replication_handler_result.message
    else:
        result.message = concatenate_if_str(
            replication_handler_message, "Updated dockerfile code."
        )

    return result


@freeze_operation_on_deprecated
def unbuild(*, current_build: ImageBuild) -> str:
    """Remove the Docker image without deleting the DB record."""
    if is_referenced(current_build):
        raise BuildInUseError("Build is referenced by an Instance or Image")
    if not current_build.is_built:
        return "OK"
    schedule_remove_if_exists_from(current_build)
    current_build.docker_image_id = None
    current_build.save(update_fields=["docker_image_id", "updated_at"])
    return "OK"


def delete_build(*, current_build: ImageBuild) -> None:
    """Delete both the Docker image and the DB record."""
    if is_referenced(current_build):
        raise BuildInUseError("Build is referenced by an Instance or Image")
    schedule_remove_if_exists_from(current_build)
    current_build.delete()


def build_from(build: ImageBuild) -> str:
    """Pull base image + build Docker image from this entity's Dockerfile.
    docker_ops.images.build has pull=True hardcoded — registry pull is handled
    inside the wrapper."""
    image_id, _logs = docker_ops.images.build(
        tag=build.tag,
        dockerfile_fileobj=text_to_fileobj(build.dockerfile_code),
    )
    return image_id


@transaction.atomic
def try_replicate_replace_if_image_divergent(
    *, current_build: ImageBuild, dockerfile_code: str
) -> TryReplicationResult:

    result = TryReplicationResult(input_build=current_build)

    image_build_result: tuple[str, Any] = docker_ops.images.build(
        tag=current_build.tag, dockerfile_fileobj=text_to_fileobj(dockerfile_code)
    )

    new_image_id: str = image_build_result[0]

    if new_image_id == current_build.docker_image_id:
        current_build.dockerfile_code = dockerfile_code
        current_build.save(update_fields=["dockerfile_code"])
        result.message = "Did not replicate. Resulting image is same."
        return result

    else:
        new_build: ImageBuild = handle_replication(  # type: ignore
            current_build=current_build,
            dockerfile_code=dockerfile_code,
            new_image_id=new_image_id,
        )

        result.new_build = new_build

        result.message = (
            "Replication successful: "
            f"new build #{new_build.pk}. "
            f" Deprecated: #{current_build.pk}"
        )

    return result


def concatenate_if_str(v1, v2, delim: str = " "):
    is_v1_str = isinstance(v1, str)
    is_v2_str = isinstance(v2, str)
    if is_v1_str and is_v2_str:
        return v1 + delim + v2
    elif is_v1_str:
        return v1
    elif is_v2_str:
        return v2
    return ""


def is_referenced(current_build: ImageBuild) -> bool:
    """True iff any Instance.image_build_in_use or Image.active_build points
    at this build. Blocks un-build and delete."""
    from ec2.subapps.images.models import Image
    from ec2.subapps.instances.models import Instance

    if Image.objects.filter(active_build=current_build).exists():
        return True
    if Instance.objects.filter(image_build_in_use=current_build).exists():
        return True
    return False


# TODO: implement actual job.


def schedule_remove_if_exists_from(current_build: ImageBuild) -> None:
    """Schedule docker image removal as a background job. Synchronous fallback
    for now — does not block on registry round-trips that already failed."""
    image_id = current_build.docker_image_id
    if not image_id:
        return
    try:
        docker_ops.images.remove(image_id)
    except docker_ops.ImageRemoveException:
        # Best-effort. Cleanup job will retry deprecated builds.
        pass


@transaction.atomic
def handle_replication(
    *, current_build: ImageBuild, dockerfile_code: str, new_image_id: str
) -> ImageBuild:
    new_build: ImageBuild = create_build_record_from(current_build)
    new_build.update(
        {"dockerfile_code": dockerfile_code, "docker_image_id": new_image_id},
    )
    current_build.update({"deprecated": True})

    update_image_references(old_build=current_build, new_build=new_build)

    return new_build


def create_build_record_from(build: ImageBuild) -> ImageBuild:
    """Clone the DB record, build a new Docker image, attach its id."""
    new_build = deepcopy(build)
    new_build.pk = None
    new_build._state.adding = True
    new_build.docker_image_id = None
    new_build.deprecated = False
    new_build.save()
    return new_build


def update_image_references(*, old_build: ImageBuild, new_build: ImageBuild) -> None:
    """Repoint every Image whose active_build == old_build to new_build."""
    from ec2.subapps.images.models import Image

    Image.objects.filter(active_build=old_build).update(active_build=new_build)


# TODO: implement actual job.


def deprecated_build_clean_up_job() -> int:
    """Periodic sweep: delete deprecated builds no longer referenced by any
    Instance or Image. Returns count of records cleaned up."""
    cleaned = 0
    for mib in ImageBuild.objects.filter(deprecated=True):
        if not is_referenced(mib):
            schedule_remove_if_exists_from(mib)
            mib.delete()
            cleaned += 1
    return cleaned
