from django.conf import settings
from django.db import models


class Instance(models.Model):
    """A running (or stopped) VM provisioned for a user.

    image_build_in_use is set at creation to image.active_build at that
    moment and never updated — an instance is tied to the exact build it
    was started from."""

    docker_container_id = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ec2_instances",
        null=True,
        blank=True,
    )

    image = models.ForeignKey(
        "ec2.Image",
        on_delete=models.PROTECT,
        related_name="instances",
    )
    image_build_in_use = models.ForeignKey(
        "ec2.ImageBuild",
        on_delete=models.PROTECT,
        related_name="instances_in_use",
    )

    cpu = models.PositiveIntegerField()
    ram = models.PositiveIntegerField(help_text="GB")
    storage = models.PositiveIntegerField(help_text="GB")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ec2"
        ordering = ["-created_at"]

    @property
    def short_id(self) -> str:
        return (self.docker_container_id or "")[:12] or f"i-{self.pk:08d}"

    def __str__(self) -> str:
        return self.name or self.short_id
