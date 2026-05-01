from django.urls import include, path

from . import admin_views, user_views

app_name = "ec2_images"

admin_patterns = [
    path("", admin_views.list_view, name="list"),
    path("create/", admin_views.create_view, name="create"),
    path("<int:pk>/", admin_views.detail_view, name="detail"),
    path("<int:pk>/update/", admin_views.update_view, name="update"),
    path("<int:pk>/delete/", admin_views.delete_view, name="delete"),
]

urlpatterns = [
    path("", user_views.list_view, name="list"),
    path("admin/", include((admin_patterns, "admin")))
]
