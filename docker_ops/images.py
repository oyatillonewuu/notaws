from typing import IO, Any

from docker.errors import APIError, BuildError

from docker_ops.client import docker_client
from docker_ops.exceptions import ImageBuildException, ImageRemoveException


def build(tag: str, dockerfile_fileobj: IO) -> tuple[str, Any]:
    try:
        image, logs = docker_client.images.build(
            tag=tag, fileobj=dockerfile_fileobj, pull=True
        )
        return (str(image.id), logs)
    except (BuildError, APIError):
        raise ImageBuildException()
    except Exception:
        raise ImageBuildException(msg="Unknown error occurred.")


def remove(image_id: str) -> None:
    try:
        docker_client.images.remove(image_id)
    except Exception:
        raise ImageRemoveException
