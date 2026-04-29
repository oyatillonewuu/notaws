"""Business logic for ImageBuild. Owns mutations of system-managed fields
(docker_image_id, deprecated) and orchestrates Docker operations through
docker_ops. Views never call docker_ops directly."""

from copy import copy

from django.db import transaction

import docker_ops
from docker_ops.utils import text_to_fileobj
from ec2.subapps.image_builds.schemas import BuildResult, RebuildReplaceResult

from .models import ImageBuild


class BuildInUseError(Exception):
    """Raised when an un-build/delete is attempted on a build that is
    referenced by an Image.active_build or any Instance.image_build_in_use."""


# --- low-level: actual Docker invocation --------------------------------


def build_from(mib_entity: ImageBuild) -> str:
    """Pull base image + build Docker image from this entity's Dockerfile.
    docker_ops.images.build has pull=True hardcoded — registry pull is handled
    inside the wrapper."""
    image_id, _logs = docker_ops.images.build(
        tag=mib_entity.tag,
        dockerfile_fileobj=text_to_fileobj(mib_entity.dockerfile_code),
    )
    return image_id


# --- mutators of system-managed fields ----------------------------------


def update_docker_image_id(mib_entity: ImageBuild, new_id: str) -> None:
    mib_entity.docker_image_id = new_id
    mib_entity.save(update_fields=["docker_image_id", "updated_at"])


# --- replication: create_build_from / rebuild_and_replace ---------------


def create_build_record_from(mib_entity: ImageBuild) -> ImageBuild:
    """Clone the DB record, build a new Docker image, attach its id."""
    new_mib = copy(mib_entity)
    new_mib.pk = None
    new_mib.docker_image_id = None
    new_mib.deprecated = False
    new_mib.save()
    return new_mib


def update_image_references(*, old_build: ImageBuild, new_build: ImageBuild) -> None:
    """Repoint every Image whose active_build == old_build to new_build."""
    from ec2.subapps.images.models import Image

    Image.objects.filter(active_build=old_build).update(active_build=new_build)


@transaction.atomic
def rebuild_and_replace(old_build: ImageBuild) -> RebuildReplaceResult:
    """Replication: build a fresh Docker image into a new ImageBuild record,
    deprecate the old one, and repoint Image.active_build references.

    Existing Instance.image_build_in_use still points at old_build — by design.
    """
    result: RebuildReplaceResult = RebuildReplaceResult(old_build=old_build)

    new_image_id = build_from(old_build)

    if new_image_id == old_build.docker_image_id:
        result.is_rebuilt_image_same = True
    else:
        new_build = create_build_record_from(old_build)
        new_build.docker_image_id = new_image_id
        new_build.save()

        old_build.deprecated = True
        old_build.save(update_fields=["deprecated", "updated_at"])
        update_image_references(old_build=old_build, new_build=new_build)
        result.new_build = new_build

    return result


# --- public lifecycle entry points --------------------------------------


def build(current_build: ImageBuild) -> BuildResult:
    if not current_build.is_built:
        new_id = build_from(current_build)
        update_docker_image_id(current_build, new_id)
        return BuildResult(old_build=current_build)
    return rebuild_and_replace(current_build)  # type: ignore


@transaction.atomic
def update_build(
    current_build: ImageBuild,
    *,
    tag: str | None = None,
    dockerfile_code: str | None = None,
):
    """Apply admin updates per the Update lifecycle rule:

    - tag change: in-place, no Docker op
    - dockerfile change OR force_rebuild: triggers rebuild_and_replace
    """
    new_build = None

    if tag is not None and tag != current_build.tag:
        current_build.tag = tag
        current_build.save()

    if dockerfile_code is not None and dockerfile_code != current_build.dockerfile_code:
        if not current_build.is_built:
            current_build.dockerfile_code = dockerfile_code
            current_build.save()
            return BuildResult(old_build=current_build)

        new_build = create_build_record_from(current_build)
        result = build(new_build)

        if new_build.docker_image_id == current_build.docker_image_id:
            current_build.dockerfile_code = dockerfile_code
            current_build.save()
            new_build.delete()
            result.is_rebuilt_image_same = True
        return result
    return BuildResult(old_build=current_build)


# --- references / un-build / delete -------------------------------------


def is_referenced(mib_entity: ImageBuild) -> bool:
    """True iff any Instance.image_build_in_use or Image.active_build points
    at this build. Blocks un-build and delete."""
    from ec2.subapps.images.models import Image
    from ec2.subapps.instances.models import Instance

    if Image.objects.filter(active_build=mib_entity).exists():
        return True
    if Instance.objects.filter(image_build_in_use=mib_entity).exists():
        return True
    return False


# TODO: implement actual job.


def schedule_remove_if_exists_from(mib_entity: ImageBuild) -> None:
    """Schedule docker image removal as a background job. Synchronous fallback
    for now — does not block on registry round-trips that already failed."""
    image_id = mib_entity.docker_image_id
    if not image_id:
        return
    try:
        docker_ops.images.remove(image_id)
    except docker_ops.ImageRemoveException:
        # Best-effort. Cleanup job will retry deprecated builds.
        pass


def unbuild(mib_entity: ImageBuild) -> str:
    """Remove the Docker image without deleting the DB record."""
    if is_referenced(mib_entity):
        raise BuildInUseError("Build is referenced by an Instance or Image")
    if not mib_entity.is_built:
        return "OK"
    schedule_remove_if_exists_from(mib_entity)
    mib_entity.docker_image_id = None
    mib_entity.save(update_fields=["docker_image_id", "updated_at"])
    return "OK"


def delete_build(mib_entity: ImageBuild) -> None:
    """Delete both the Docker image and the DB record."""
    if is_referenced(mib_entity):
        raise BuildInUseError("Build is referenced by an Instance or Image")
    schedule_remove_if_exists_from(mib_entity)
    mib_entity.delete()


# --- background cleanup -------------------------------------------------

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
