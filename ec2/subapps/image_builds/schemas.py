from dataclasses import dataclass

from .models import ImageBuild


@dataclass
class RebuildReplaceResult:
    old_build: ImageBuild
    new_build: ImageBuild | None = None
    is_rebuilt_image_same: bool = False

class BuildResult(RebuildReplaceResult):
    pass
