from .enums import ResultStatus
from .exceptions import ImageNotReadyError, InstanceHasNoContainerError
from .models import Instance
from .schemas import (
    CreateResult,
    DeleteResult,
    StartResult,
    StopResult,
    UpdateResult,
)
from .tasks import (
    dispatch_container_create,
    dispatch_container_remove,
    dispatch_container_start,
    dispatch_container_stop,
)
from .utils import get_container_status_from, update_container_resources_from

MAX_CPU = 4
MAX_RAM = 8      # GB
MAX_STORAGE = 100  # GB


def create_instance(
    *, image, ram: int, cpu: int, storage: int, owner, name: str | None = None
) -> CreateResult:
    if not image.active_build or not image.active_build.is_built:
        raise ImageNotReadyError("Selected image has no built active build")

    instance = Instance(
        owner=owner,
        image=image,
        image_build_in_use=image.active_build,
        ram=ram,
        cpu=cpu,
        storage=storage,
        name=name,
    )
    instance.save()

    dispatch_container_create(instance_id=instance.pk)

    return CreateResult(
        status=ResultStatus.success,
        instance_pk=instance.pk,
        message="Instance created and started.",
    )


def update_instance(
    *,
    instance: Instance,
    name: str | None,
    cpu: int | None,
    ram: int | None,
    storage: int | None,
) -> UpdateResult:
    resources_changed = (
        (cpu is not None and cpu != instance.cpu)
        or (ram is not None and ram != instance.ram)
    )

    if name is not None:
        instance.name = name
    if cpu is not None:
        instance.cpu = cpu
    if ram is not None:
        instance.ram = ram
    if storage is not None:
        instance.storage = storage

    instance.save()

    if resources_changed and instance.docker_container_id:
        update_container_resources_from(instance)

    return UpdateResult(status=ResultStatus.success, message="Instance updated.")


def start_instance(*, instance: Instance) -> StartResult:
    dispatch_container_start(instance_id=instance.pk)
    return StartResult(status=ResultStatus.success, message="Instance started.")


def stop_instance(*, instance: Instance) -> StopResult:
    dispatch_container_stop(instance_id=instance.pk)
    return StopResult(status=ResultStatus.success, message="Instance stopped.")


def delete_instance(*, instance: Instance) -> DeleteResult:
    container_id = instance.docker_container_id
    if container_id:
        dispatch_container_remove(container_id=container_id)

    instance.delete()
    return DeleteResult(status=ResultStatus.success, message="Instance deleted.")


def get_instance_status(*, instance: Instance) -> str:
    return get_container_status_from(instance)
