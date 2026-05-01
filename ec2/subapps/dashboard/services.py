from django.db import OperationalError, ProgrammingError

from ec2.models import Image, ImageBuild, Instance


def get_dashboard_data() -> dict:
    default = {
        "database_ready": False,
        "stats": [
            {"label": "Images", "value": 0, "detail": "No database tables yet"},
            {"label": "Builds", "value": 0, "detail": "Run migrations to initialize"},
            {
                "label": "Instances",
                "value": 0,
                "detail": "No runtime activity available",
            },
        ],
        "recent_instances": [],
    }

    try:
        instances = list(
            Instance.objects.select_related("image", "image_build_in_use", "owner")[:5]
        )
        return {
            "database_ready": True,
            "stats": [
                {
                    "label": "Images",
                    "value": Image.objects.count(),
                    "detail": "Catalog entries available",
                },
                {
                    "label": "Builds",
                    "value": ImageBuild.objects.count(),
                    "detail": "Pipelines configured",
                },
                {
                    "label": "Instances",
                    "value": Instance.objects.count(),
                    "detail": "Provisioned workloads",
                },
            ],
            "recent_instances": instances,
        }
    except (OperationalError, ProgrammingError):
        return default
