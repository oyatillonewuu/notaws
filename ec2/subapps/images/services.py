"""Business logic for Image. Mostly thin — Image is a pointer record.

Reassigning active_build does NOT migrate existing Instances; Instances hold
image_build_in_use as a snapshot at creation time."""
from .models import Image


class ImageInUseError(Exception):
    """Raised when deleting an Image that has live Instances."""


def has_live_instances(image: Image) -> bool:
    from ec2.subapps.instances.models import Instance
    return Instance.objects.filter(image=image).exists()


def delete_image(image: Image) -> None:
    if has_live_instances(image):
        raise ImageInUseError("Image is in use by one or more Instances")
    image.delete()


def selectable_builds_qs():
    """ImageBuild rows admins can attach as active_build:
    must be built and not deprecated."""
    from ec2.subapps.image_builds.models import ImageBuild
    return ImageBuild.objects.filter(deprecated=False).exclude(docker_image_id__isnull=True)


def selectable_images_for_instance_qs():
    """Images users can choose when creating an Instance:
    active_build must exist and be built/non-deprecated."""
    return Image.objects.filter(
        active_build__isnull=False,
        active_build__deprecated=False,
    ).exclude(active_build__docker_image_id__isnull=True)
