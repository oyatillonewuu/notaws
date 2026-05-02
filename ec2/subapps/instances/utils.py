from django.contrib import messages

import docker_ops
from docker_ops.exceptions import ContainerOpException

from .exceptions import InstanceHasNoContainerError
from .models import Instance
from .schemas import GenericServiceFunctionResult


def create_container_from(instance: Instance) -> str:
    """Create and start a Docker container from the instance's snapshot build."""
    image_id = instance.image_build_in_use.docker_image_id
    return docker_ops.containers.create_container(
        image_id=image_id,
        cpu=instance.cpu,
        ram=instance.ram,
        storage=instance.storage,
    )


def start_container_from(instance: Instance) -> None:
    if not instance.docker_container_id:
        raise InstanceHasNoContainerError("Instance has no container assigned yet")
    docker_ops.containers.start_container(instance.docker_container_id)


def stop_container_from(instance: Instance) -> None:
    if not instance.docker_container_id:
        raise InstanceHasNoContainerError("Instance has no container assigned yet")
    docker_ops.containers.stop_container(instance.docker_container_id)


def update_container_resources_from(instance: Instance) -> None:
    """Live-update the container's CPU/RAM to match the instance row."""
    if not instance.docker_container_id:
        return
    docker_ops.containers.update_container_resources(
        instance.docker_container_id,
        cpu=instance.cpu,
        ram=instance.ram,
    )


def remove_container_if_exists(container_id: str | None) -> None:
    """Best-effort removal — silently eats ContainerOpException."""
    if not container_id:
        return
    try:
        docker_ops.containers.remove_container(container_id)
    except ContainerOpException:
        pass


def get_container_status_from(instance: Instance) -> str:
    if not instance.docker_container_id:
        return "pending"
    try:
        return docker_ops.containers.get_container_status(instance.docker_container_id)
    except ContainerOpException:
        return "unknown"


def set_django_message_from_result(
    *, request, service_result: GenericServiceFunctionResult
):
    message_setter = getattr(messages, str(service_result.status))
    message_setter(request, service_result.message)
