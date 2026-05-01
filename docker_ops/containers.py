"""Docker container operations. Wraps docker_client.containers."""
import docker

from .client import docker_client
from .exceptions import ContainerCreateException, ContainerOpException


def create_container(image_id: str, cpu: int, ram: int, storage: int) -> str:
    """Create and start a container from a Docker image. Returns the container ID.

    cpu: vCPU cores (maps to nano_cpus)
    ram: RAM in GB (maps to mem_limit)
    storage: GB — tracked as a container label; not enforced at the Docker layer
    """
    try:
        container = docker_client.containers.run(
            image=image_id,
            detach=True,
            stdin_open=True,
            tty=True,
            mem_limit=f"{ram}g",
            nano_cpus=int(cpu * 1e9),
            labels={"notaws.storage_gb": str(storage)},
        )
    except docker.errors.ImageNotFound as exc:
        raise ContainerCreateException(f"Image {image_id!r} not found: {exc}") from exc
    except docker.errors.APIError as exc:
        raise ContainerCreateException(
            f"Failed to create container from {image_id!r}: {exc}"
        ) from exc
    return container.id


def start_container(container_id: str) -> None:
    try:
        container = docker_client.containers.get(container_id)
        container.start()
    except docker.errors.NotFound as exc:
        raise ContainerOpException(f"Container {container_id!r} not found: {exc}") from exc
    except docker.errors.APIError as exc:
        raise ContainerOpException(
            f"Failed to start container {container_id!r}: {exc}"
        ) from exc


def stop_container(container_id: str) -> None:
    try:
        container = docker_client.containers.get(container_id)
        container.stop()
    except docker.errors.NotFound as exc:
        raise ContainerOpException(f"Container {container_id!r} not found: {exc}") from exc
    except docker.errors.APIError as exc:
        raise ContainerOpException(
            f"Failed to stop container {container_id!r}: {exc}"
        ) from exc


def remove_container(container_id: str) -> None:
    """Remove a container. No-ops if already gone."""
    try:
        container = docker_client.containers.get(container_id)
        container.remove(force=True)
    except docker.errors.NotFound:
        return
    except docker.errors.APIError as exc:
        raise ContainerOpException(
            f"Failed to remove container {container_id!r}: {exc}"
        ) from exc


def get_container_status(container_id: str) -> str:
    """Return the container status string (e.g. 'running', 'exited', 'created')."""
    try:
        container = docker_client.containers.get(container_id)
        return container.status
    except docker.errors.NotFound:
        return "not_found"
    except docker.errors.APIError as exc:
        raise ContainerOpException(
            f"Failed to get status for container {container_id!r}: {exc}"
        ) from exc


def exec_interactive(container_id: str, cmd: str = "/bin/sh"):
    """Open an interactive TTY exec session. Returns (exec_id, sock).

    exec_id: dict with 'Id' key (pass to resize_exec)
    sock: docker-py SocketIO; raw Python socket at sock._sock
    In TTY mode output is raw bytes with no multiplexing header.
    """
    try:
        container = docker_client.containers.get(container_id)
        if container.status != "running":
            container.start()
        exec_id = docker_client.api.exec_create(
            container_id,
            cmd,
            stdin=True,
            tty=True,
            stdout=True,
            stderr=True,
        )
        sock = docker_client.api.exec_start(exec_id, socket=True, tty=True)
        return exec_id, sock
    except docker.errors.NotFound as exc:
        raise ContainerOpException(f"Container {container_id!r} not found: {exc}") from exc
    except docker.errors.APIError as exc:
        raise ContainerOpException(f"Failed to exec into {container_id!r}: {exc}") from exc


def resize_exec(exec_id, *, rows: int, cols: int) -> None:
    """Resize the TTY for an exec session. Silently ignores errors."""
    try:
        docker_client.api.exec_resize(exec_id, height=rows, width=cols)
    except docker.errors.APIError:
        pass
