"""Business logic for ImageBuild. Owns mutations of system-managed fields
(docker_image_id, deprecated) and orchestrates Docker operations through
docker_ops. Views never call docker_ops directly."""
from copy import copy

from django.db import transaction

import docker_ops
from docker_ops.utils import text_to_fileobj

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


def create_build_from(mib_entity: ImageBuild) -> ImageBuild:
    """Clone the DB record, build a new Docker image, attach its id."""
    new_mib = copy(mib_entity)
    new_mib.pk = None
    new_mib.docker_image_id = None
    new_mib.deprecated = False
    new_mib.save()

    image_id = build_from(new_mib)
    new_mib.docker_image_id = image_id
    new_mib.save(update_fields=["docker_image_id", "updated_at"])
    return new_mib


def update_image_references(*, old_build: ImageBuild, new_build: ImageBuild) -> None:
    """Repoint every Image whose active_build == old_build to new_build."""
    from ec2.subapps.images.models import Image
    Image.objects.filter(active_build=old_build).update(active_build=new_build)


@transaction.atomic
def rebuild_and_replace(old_build: ImageBuild) -> ImageBuild:
    """Replication: build a fresh Docker image into a new ImageBuild record,
    deprecate the old one, and repoint Image.active_build references.

    Existing Instance.image_build_in_use still points at old_build — by design.
    """
    new_build = create_build_from(old_build)
    old_build.deprecated = True
    old_build.save(update_fields=["deprecated", "updated_at"])
    update_image_references(old_build=old_build, new_build=new_build)
    return new_build


# --- public lifecycle entry points --------------------------------------


def build(mib_entity: ImageBuild):
    """Central operation. Branches on is_built.

    Returns (mib_entity, new_build_or_None). new_build is non-None only on
    rebuild, where the caller should usually navigate to the new record.
    """
    if not mib_entity.is_built:
        new_id = build_from(mib_entity)
        update_docker_image_id(mib_entity, new_id)
        return (mib_entity, None)
    new_build = rebuild_and_replace(mib_entity)
    return (mib_entity, new_build)


def update_build(
    mib_entity: ImageBuild,
    *,
    tag: str | None = None,
    dockerfile_code: str | None = None,
    force_rebuild: bool = False,
):
    """Apply admin updates per the Update lifecycle rule:

      - tag change: in-place, no Docker op
      - dockerfile change OR force_rebuild: triggers rebuild_and_replace
    """
    new_build = None
    rebuild_needed = force_rebuild

    if tag is not None and tag != mib_entity.tag:
        mib_entity.tag = tag

    # FIX: this way of updaing is wrong. It contradicts append-only
    # #    rule.
    # #    Expected behavior: create new build if there is a change in docker file.
    # #    Also, this needs to be checked with is_built.
    # #    If the build is not built, we do update docker file. We don't handler
    # #    rebuild case.
    # TODO: later: move the logic of checking dockerfile code to a separate function.

    if dockerfile_code is not None and dockerfile_code != mib_entity.dockerfile_code:
        mib_entity.dockerfile_code = dockerfile_code
        rebuild_needed = True

    mib_entity.save()

    if rebuild_needed and mib_entity.is_built:
        new_build = rebuild_and_replace(mib_entity)
    # FIX: This is totally wrong.
    elif rebuild_needed and not mib_entity.is_built:
        new_id = build_from(mib_entity)
        update_docker_image_id(mib_entity, new_id)

    return (mib_entity, new_build)


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
