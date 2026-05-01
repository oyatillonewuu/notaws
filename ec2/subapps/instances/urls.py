from django.urls import path

from . import user_views

app_name = "ec2_instances"

urlpatterns = [
    path("", user_views.index_view, name="index"),
]
