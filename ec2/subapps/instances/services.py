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
from .utils import get_container_status_from

MAX_CPU = 4
MAX_RAM = 8      # GB
MAX_STORAGE = 100  # GB


def create_instance(
    *, image, ram: int, cpu: int, storage: int, owner, name: str | None = None
) -> CreateResult:
    result = CreateResult()
    result.status = ResultStatus.warning

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

    result.instance_pk = instance.pk
    result.message = "Instance created. Container is starting."
    return result


def update_instance(
    *,
    instance: Instance,
    name: str | None,
    cpu: int | None,
    ram: int | None,
    storage: int | None,
) -> UpdateResult:
    result = UpdateResult()

    if name is not None:
        instance.name = name
    if cpu is not None:
        instance.cpu = cpu
    if ram is not None:
        instance.ram = ram
    if storage is not None:
        instance.storage = storage

    instance.save()
    result.message = "Instance updated."
    return result


def start_instance(*, instance: Instance) -> StartResult:
    result = StartResult()
    result.status = ResultStatus.warning
    dispatch_container_start(instance_id=instance.pk)
    result.message = "Start queued."
    return result


def stop_instance(*, instance: Instance) -> StopResult:
    result = StopResult()
    result.status = ResultStatus.warning
    dispatch_container_stop(instance_id=instance.pk)
    result.message = "Stop queued."
    return result


def delete_instance(*, instance: Instance) -> DeleteResult:
    result = DeleteResult()
    result.status = ResultStatus.warning
    result.message = ""

    container_id = instance.docker_container_id
    if container_id:
        dispatch_container_remove(container_id=container_id)
        result.message = "Container removal queued. "

    instance.delete()
    result.message += "DB record deleted."
    return result


def get_instance_status(*, instance: Instance) -> str:
    return get_container_status_from(instance)
