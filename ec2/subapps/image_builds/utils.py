import functools
from copy import deepcopy

from django.contrib import messages
from django.db import transaction

import docker_ops
from docker_ops.utils import text_to_fileobj

from .exceptions import CannotOperateOnDeprecatedBuild
from .models import ImageBuild
from .schemas import GenericServiceFunctionResult, TryReplicationResult


def freeze_operation_on_deprecated(build_var_name: str = "current_build"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_build = kwargs.get(build_var_name)
            if current_build is not None and current_build.deprecated:
                raise CannotOperateOnDeprecatedBuild(
                    "Cannot carry this operation. Build is deprecated."
                )
            result = func(*args, **kwargs)

            return result

        return wrapper

    return decorator


def build_from(build: ImageBuild) -> str:
    """Pull base image + build Docker image from this entity's Dockerfile.
    docker_ops.images.build has pull=True hardcoded — registry pull is handled
    inside the wrapper."""
    image_id, _logs = docker_ops.images.build(
        tag=build.tag,
        dockerfile_fileobj=text_to_fileobj(build.dockerfile_code),
    )
    return image_id


def create_build_record_from(build: ImageBuild) -> ImageBuild:
    """Clone the DB record, build a new Docker image, attach its id."""
    new_build = deepcopy(build)
    new_build.pk = None
    new_build._state.adding = True
    new_build.docker_image_id = None
    new_build.deprecated = False
    new_build.save()
    return new_build


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


def remove_docker_image_if_exists(image_id: str) -> None:
    """Schedule docker image removal as a background job. Synchronous fallback
    for now — does not block on registry round-trips that already failed."""
    if not image_id:
        return
    try:
        docker_ops.images.remove(image_id)
    except docker_ops.ImageRemoveException:
        # Best-effort. Cleanup job will retry deprecated builds.
        pass


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


def update_image_references(*, old_build: ImageBuild, new_build: ImageBuild) -> None:
    """Repoint every Image whose active_build == old_build to new_build."""
    from ec2.subapps.images.models import Image

    Image.objects.filter(active_build=old_build).update(active_build=new_build)


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


def set_django_message_from_result(
    *, request, service_result: GenericServiceFunctionResult
):
    message_setter = getattr(messages, str(service_result.status))
    message_setter(request, service_result.message)
