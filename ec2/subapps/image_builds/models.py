from typing import Any

from django.db import models

# TODO: add status field for building


class ImageBuild(models.Model):
    """One concrete build of a Docker image from a Dockerfile.

    docker_image_id, deprecated, and is_built are SYSTEM-MANAGED — only
    service logic mutates them. tag and dockerfile_code are admin-editable.
    """

    tag = models.CharField(max_length=255)
    dockerfile_code = models.TextField()

    docker_image_id = models.CharField(max_length=255, null=True, blank=True)
    deprecated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ec2"
        ordering = ["-created_at"]

    @property
    def is_built(self) -> bool:
        return self.docker_image_id is not None

    def update(self, field_values_kv: dict[str, Any]):
        for field, value in field_values_kv.items():
            if not hasattr(self, field):
                raise AttributeError(
                    f"Updating field error: no such attribute '{field}' in {self}.name="
                )
            setattr(self, field, value)

        update_fields = list(field_values_kv.keys()) + ["updated_at"]

        self.save(update_fields=update_fields)

    def __str__(self) -> str:
        return f"{self.tag} ({'built' if self.is_built else 'unbuilt'})"
