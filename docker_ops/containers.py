"""Docker container operations. Wraps docker_client.containers."""
import os

import docker

from .client import docker_client
from .exceptions import ContainerCreateException, ContainerOpException

# lxcfs makes /proc inside containers reflect cgroup limits instead of the
# host kernel's view. Without it, neofetch / free / nproc show the host's
# CPU + RAM, which breaks the VM illusion. If lxcfs isn't installed on the
# host, _lxcfs_volumes() returns nothing and containers fall back silently.
LXCFS_PROC_DIR = "/var/lib/lxcfs/proc"
LXCFS_PROC_FILES = ("cpuinfo", "meminfo", "uptime", "stat", "diskstats", "swaps", "loadavg")


def _lxcfs_volumes() -> dict:
    if not os.path.isdir(LXCFS_PROC_DIR):
        return {}
    volumes = {}
    for name in LXCFS_PROC_FILES:
        host_path = f"{LXCFS_PROC_DIR}/{name}"
        if os.path.exists(host_path):
            volumes[host_path] = {"bind": f"/proc/{name}", "mode": "rw"}
    return volumes


def create_container(image_id: str, cpu: int, ram: int, storage: int) -> str:
    """Create and start a container from a Docker image. Returns the container ID.

    cpu: vCPU cores (maps to nano_cpus)
    ram: RAM in GB (maps to mem_limit)
    storage: GB — tracked as a container label; not enforced at the Docker layer
    """
    volumes = _lxcfs_volumes() or None
    try:
        container = docker_client.containers.run(
            image=image_id,
            detach=True,
            stdin_open=True,
            tty=True,
            mem_limit=f"{ram}g",
            memswap_limit=f"{ram}g",
            nano_cpus=int(cpu * 1e9),
            labels={"notaws.storage_gb": str(storage)},
            volumes=volumes,
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


def update_container_resources(container_id: str, *, cpu: int, ram: int) -> None:
    """Live-update CPU and RAM limits on a running or stopped container.

    Storage is not updated here — it's tracked as a label only and not
    enforced at the Docker layer (would require overlay2 + storage-opt).
    """
    try:
        docker_client.api.update_container(
            container_id,
            mem_limit=f"{ram}g",
            memswap_limit=f"{ram}g",
            cpu_quota=int(cpu * 100_000),
            cpu_period=100_000,
        )
    except docker.errors.NotFound as exc:
        raise ContainerOpException(f"Container {container_id!r} not found: {exc}") from exc
    except docker.errors.APIError as exc:
        raise ContainerOpException(
            f"Failed to update container {container_id!r}: {exc}"
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


def exec_interactive(container_id: str, cmd: list[str] | str | None = None):
    """Open an interactive TTY exec session. Returns (exec_id, sock).

    exec_id: dict with 'Id' key (pass to resize_exec)
    sock: docker-py SocketIO; raw Python socket at sock._sock
    In TTY mode output is raw bytes with no multiplexing header.

    Default tries bash (line editing, history, tab completion); falls back to
    sh if the image doesn't have bash. We don't use `bash -l` — login mode
    sources /etc/profile + friends and on a stripped image that produces a
    silent shell with no prompt and no input echo (PTY ends up in raw mode).
    """
    candidates = [cmd] if cmd is not None else [["bash"], ["sh"]]
    try:
        container = docker_client.containers.get(container_id)
        if container.status != "running":
            container.start()
        last_exc: Exception | None = None
        for candidate in candidates:
            try:
                exec_id = docker_client.api.exec_create(
                    container_id,
                    candidate,
                    stdin=True,
                    tty=True,
                    stdout=True,
                    stderr=True,
                    environment={"TERM": "xterm-256color"},
                )
                sock = docker_client.api.exec_start(exec_id, socket=True, tty=True)
                return exec_id, sock
            except docker.errors.APIError as exc:
                last_exc = exc
                continue
        raise ContainerOpException(
            f"No usable shell in {container_id!r}: {last_exc}"
        ) from last_exc
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
