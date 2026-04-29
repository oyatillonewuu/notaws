"""Docker image operations. Wraps docker_client.images and re-raises
APIError/BuildError as ImageBuild/ImageRemove exceptions."""
from typing import IO, Any

import docker

from .client import docker_client
from .exceptions import ImageBuildException, ImageRemoveException


def build(tag: str, dockerfile_fileobj: IO) -> tuple[str, Any]:
    """Build a Docker image. pull=True is hardcoded — always pulls the base
    image from the registry before building."""
    try:
        image, logs = docker_client.images.build(
            tag=tag,
            fileobj=dockerfile_fileobj,
            pull=True,
            rm=True,
            forcerm=True
        )
        print(image.id)
    except docker.errors.BuildError as exc:
        raise ImageBuildException(f"Build failed for tag {tag!r}: {exc}") from exc
    except docker.errors.APIError as exc:
        raise ImageBuildException(f"Docker API error building {tag!r}: {exc}") from exc
    return (str(image.id), logs)


def remove(image_id: str) -> None:
    try:
        docker_client.images.remove(image=image_id, force=False)
    except docker.errors.ImageNotFound:
        return
    except docker.errors.APIError as exc:
        raise ImageRemoveException(f"Failed to remove image {image_id!r}: {exc}") from exc


def exists(image_id: str) -> bool:
    try:
        docker_client.images.get(image_id)
        return True
    except docker.errors.ImageNotFound:
        return False
    # FIX: must raise error
    except docker.errors.APIError:
        return False
