from django.urls import path

from . import admin_views

app_name = "ec2_image_builds"

urlpatterns = [
    path("", admin_views.list_view, name="list"),
    path("create/", admin_views.create_view, name="create"),
    path("<int:pk>/", admin_views.detail_view, name="detail"),
    path("<int:pk>/update-direct/", admin_views.update_direct, name="update_direct"),
    path(
        "<int:pk>/update-dockerfile-code/",
        admin_views.update_dockerfile_code,
        name="update_dockerfile_code",
    ),
    path("<int:pk>/build/", admin_views.build_view, name="build"),
    path("<int:pk>/unbuild/", admin_views.unbuild_view, name="unbuild"),
    path("<int:pk>/delete/", admin_views.delete_view, name="delete"),
]
