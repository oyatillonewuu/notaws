from .models import ImageBuild
from .schemas import TryReplicationResult
from .utils import (
    build_from,
    remove_docker_image_if_exists,
    try_replicate_replace_if_image_divergent,
)


def dispatch_build(*, build: ImageBuild):
    new_id = build_from(build)
    build.update({"docker_image_id": new_id})
    # Do some updates like ImageBuild status, etc.


def dispatch_replication(*, current_build: ImageBuild, dockerfile_code: str):
    result: TryReplicationResult = try_replicate_replace_if_image_divergent(  # type: ignore
        current_build=current_build, dockerfile_code=dockerfile_code
    )

    # Do some updates like ImageBuild status, etc.


def dispatch_image_remove(*, image_id: str):
    remove_docker_image_if_exists(image_id=image_id)

    # Do whatever is needed.
