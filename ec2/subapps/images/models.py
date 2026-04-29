from django.db import models


class Image(models.Model):
    """A generic VM template (e.g. "Ubuntu 22.04") — a named pointer to the
    current ImageBuild. Holds no Dockerfile logic itself."""

    name = models.CharField(max_length=255)
    active_build = models.ForeignKey(
        "ec2.ImageBuild",
        on_delete=models.PROTECT,
        related_name="images_using",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ec2"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
