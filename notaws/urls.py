"""
URL configuration for notaws project.
"""

from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from . import site_views

urlpatterns = [
    path("", site_views.home_view, name="home"),
    path("signup/", site_views.signup_view, name="signup"),
    path("welcome/", site_views.welcome_view, name="welcome"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("services/ec2/", include("ec2.subapps.urls")),
    path("admin/", admin.site.urls),
]
