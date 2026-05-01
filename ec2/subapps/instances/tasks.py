from .models import Instance
from .utils import (
    create_container_from,
    remove_container_if_exists,
    start_container_from,
    stop_container_from,
)


def dispatch_container_create(*, instance_id: int) -> None:
    instance = Instance.objects.get(pk=instance_id)
    container_id = create_container_from(instance)
    instance.update({"docker_container_id": container_id})
    # Do state updates (e.g. status field) here when added.


def dispatch_container_start(*, instance_id: int) -> None:
    instance = Instance.objects.get(pk=instance_id)
    start_container_from(instance)
    # Do state updates here when added.


def dispatch_container_stop(*, instance_id: int) -> None:
    instance = Instance.objects.get(pk=instance_id)
    stop_container_from(instance)
    # Do state updates here when added.


def dispatch_container_remove(*, container_id: str) -> None:
    remove_container_if_exists(container_id)
    # Do cleanup here when needed.
