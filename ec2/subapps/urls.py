"""Aggregates subapp URL patterns under /ec2/."""
from django.urls import include, path

urlpatterns = [
    path("", include("ec2.subapps.home.urls")),
    path("images/", include("ec2.subapps.images.urls")),
    path("image-builds/", include("ec2.subapps.image_builds.urls")),
    path("instances/", include("ec2.subapps.dashboard.urls")),
    path("dashboard/", include("ec2.subapps.instances.urls")),
]
