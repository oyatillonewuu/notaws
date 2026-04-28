"""Aggregates subapp URL patterns under /ec2/."""
from django.urls import include, path

urlpatterns = [
    path("image-builds/", include("ec2.subapps.image_builds.urls")),
    path("images/", include("ec2.subapps.images.urls")),
    path("instances/", include("ec2.subapps.instances.urls")),
]
