from django.db import OperationalError, ProgrammingError

from ec2.models import Image, ImageBuild, Instance

DEFAULT_SUMMARY = {
    "database_ready": False,
    "images": 0,
    "image_builds": 0,
    "instances": 0,
}


def get_platform_summary() -> dict[str, int | bool]:
    try:
        return {
            "database_ready": True,
            "images": Image.objects.count(),
            "image_builds": ImageBuild.objects.count(),
            "instances": Instance.objects.count(),
        }
    except (OperationalError, ProgrammingError):
        return DEFAULT_SUMMARY.copy()
