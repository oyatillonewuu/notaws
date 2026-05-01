"""Users only consume Images via the Instance create form (dropdown).
No standalone user pages — see services.selectable_images_for_instance_qs."""

from django.shortcuts import render

from .models import Image


def list_view(request):
    images = Image.objects.filter(active_build__isnull=False).all()
    return render(request, "ec2/images/list_public.html", {"images": images})
