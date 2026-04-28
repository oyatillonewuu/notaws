from django.urls import include, path

urlpatterns = [path("", include("ec2.subapps.urls"))]
