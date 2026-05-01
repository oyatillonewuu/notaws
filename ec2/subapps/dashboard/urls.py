from django.urls import path

from . import user_views

app_name = "ec2_dashboard"

urlpatterns = [
    path("", user_views.home_view, name="home"),
]
