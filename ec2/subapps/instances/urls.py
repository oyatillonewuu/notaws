from django.urls import path

from . import user_views

app_name = "ec2_instances"

urlpatterns = [
    path("", user_views.list_view, name="list"),
    path("create/", user_views.create_view, name="create"),
    path("<int:pk>/", user_views.detail_view, name="detail"),
    path("<int:pk>/update/", user_views.update_view, name="update"),
    path("<int:pk>/start/", user_views.start_view, name="start"),
    path("<int:pk>/stop/", user_views.stop_view, name="stop"),
    path("<int:pk>/delete/", user_views.delete_view, name="delete"),
    path("<int:pk>/terminal/", user_views.terminal_view, name="terminal"),
]
