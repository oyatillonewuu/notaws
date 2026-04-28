"""Docker container operations. Wraps docker_client.containers and re-raises
APIError as Container*Exception variants."""
import docker

from .client import docker_client
from .exceptions import (
    ContainerCreateException,
    ContainerInspectException,
    ContainerRemoveException,
    ContainerStartException,
    ContainerStopException,
)


def _ram_to_bytes(ram_gb: int) -> int:
    return int(ram_gb) * 1024 * 1024 * 1024


def create_container(image_id: str, cpu: int, ram: int, storage: int) -> str:
    """Create a container from a Docker image with resource limits.
    Returns the container ID. Container is created but not started."""
    try:
        container = docker_client.containers.create(
            image=image_id,
            detach=True,
            tty=True,
            stdin_open=True,
            mem_limit=_ram_to_bytes(ram),
            nano_cpus=int(cpu) * 1_000_000_000,
            storage_opt={"size": f"{storage}G"} if storage else None,
        )
    except docker.errors.APIError as exc:
        raise ContainerCreateException(
            f"Failed to create container from {image_id!r}: {exc}"
        ) from exc
    return str(container.id)


def start(container_id: str) -> None:
    try:
        docker_client.containers.get(container_id).start()
    except docker.errors.NotFound as exc:
        raise ContainerStartException(f"Container not found: {container_id!r}") from exc
    except docker.errors.APIError as exc:
        raise ContainerStartException(
            f"Failed to start container {container_id!r}: {exc}"
        ) from exc


def stop(container_id: str) -> None:
    try:
        docker_client.containers.get(container_id).stop()
    except docker.errors.NotFound:
        return
    except docker.errors.APIError as exc:
        raise ContainerStopException(
            f"Failed to stop container {container_id!r}: {exc}"
        ) from exc


def remove(container_id: str) -> None:
    try:
        docker_client.containers.get(container_id).remove(force=True)
    except docker.errors.NotFound:
        return
    except docker.errors.APIError as exc:
        raise ContainerRemoveException(
            f"Failed to remove container {container_id!r}: {exc}"
        ) from exc


def get_status(container_id: str) -> str:
    try:
        container = docker_client.containers.get(container_id)
        container.reload()
        return container.status
    except docker.errors.NotFound:
        return "missing"
    except docker.errors.APIError as exc:
        raise ContainerInspectException(
            f"Failed to inspect container {container_id!r}: {exc}"
        ) from exc
