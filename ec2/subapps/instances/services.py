"""Business logic for Instance. Wraps docker_ops.containers and snapshots
image_build_in_use at creation time per the lifecycle spec."""
from django.conf import settings
from django.db import transaction

import docker_ops

from .models import Instance


class ResourceLimitError(Exception):
    """Raised when CPU/RAM/storage exceeds configured caps."""


class ImageNotReadyError(Exception):
    """Raised when an Image's active_build isn't built or is missing."""


def _check_limits(cpu: int, ram: int, storage: int) -> None:
    if cpu < 1 or cpu > settings.EC2_MAX_CPU:
        raise ResourceLimitError(f"cpu must be 1..{settings.EC2_MAX_CPU}")
    if ram < 1 or ram > settings.EC2_MAX_RAM_GB:
        raise ResourceLimitError(f"ram must be 1..{settings.EC2_MAX_RAM_GB} GB")
    if storage < 1 or storage > settings.EC2_MAX_STORAGE_GB:
        raise ResourceLimitError(f"storage must be 1..{settings.EC2_MAX_STORAGE_GB} GB")


def schedule_container_creation_from(instance: Instance) -> str:
    """Create the Docker container synchronously for now (the doc names this
    'schedule_*' to leave room for an async job queue later). Returns the
    container ID; the instance record exists in DB before this call."""
    image_id = instance.image_build_in_use.docker_image_id
    return docker_ops.containers.create_container(
        image_id=image_id,
        cpu=instance.cpu,
        ram=instance.ram,
        storage=instance.storage,
    )


@transaction.atomic
def create_instance(*, owner, image, name, cpu, ram, storage) -> Instance:
    _check_limits(cpu, ram, storage)
    if image.active_build is None or not image.active_build.docker_image_id:
        raise ImageNotReadyError("Selected Image has no built active_build")

    instance = Instance(
        owner=owner,
        name=name or None,
        image=image,
        image_build_in_use=image.active_build,  # snapshot
        cpu=cpu,
        ram=ram,
        storage=storage,
    )
    instance.save()

    container_id = schedule_container_creation_from(instance)
    instance.docker_container_id = container_id
    instance.save(update_fields=["docker_container_id", "updated_at"])
    return instance


def update_instance(
    instance: Instance, *, name=None, cpu=None, ram=None, storage=None,
) -> Instance:
    new_cpu = cpu if cpu is not None else instance.cpu
    new_ram = ram if ram is not None else instance.ram
    new_storage = storage if storage is not None else instance.storage
    _check_limits(new_cpu, new_ram, new_storage)

    if name is not None:
        instance.name = name or None
    instance.cpu = new_cpu
    instance.ram = new_ram
    instance.storage = new_storage
    instance.save()
    return instance


# --- operations: start / stop / delete / get_status ---------------------


def start(instance: Instance) -> None:
    """Equivalent to restart per the spec."""
    if not instance.docker_container_id:
        return
    docker_ops.containers.start(instance.docker_container_id)


def stop(instance: Instance) -> None:
    if not instance.docker_container_id:
        return
    docker_ops.containers.stop(instance.docker_container_id)


def schedule_delete(instance: Instance) -> None:
    """Schedules Docker container removal (background) and deletes the DB
    record. Doc says delete is non-blocking; we run it inline for now."""
    if instance.docker_container_id:
        try:
            docker_ops.containers.remove(instance.docker_container_id)
        except docker_ops.ContainerRemoveException:
            pass
    instance.delete()


def get_status(instance: Instance) -> str:
    if not instance.docker_container_id:
        return "pending"
    try:
        return docker_ops.containers.get_status(instance.docker_container_id)
    except docker_ops.DockerOpsException:
        return "unknown"
