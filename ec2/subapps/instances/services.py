from django.db import OperationalError, ProgrammingError

from ec2.models import Instance


def get_instances_page_data() -> dict:
    default = {
        "database_ready": False,
        "instances": [],
    }

    try:
        instances = list(
            Instance.objects.select_related("image", "image_build_in_use", "owner")
        )
        return {
            "database_ready": True,
            "instances": instances,
        }
    except (OperationalError, ProgrammingError):
        return default
