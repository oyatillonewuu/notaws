"""Admin-facing views for Image. Users only see the read-only dropdown
when creating an Instance."""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from . import services
from .models import Image


@staff_member_required
def list_view(request):
    images = Image.objects.select_related("active_build").all()
    return render(request, "ec2/images/list.html", {"images": images})


@staff_member_required
def detail_view(request, pk):
    image = get_object_or_404(Image.objects.select_related("active_build"), pk=pk)
    has_instances = services.has_live_instances(image)
    return render(
        request,
        "ec2/images/detail.html",
        {"image": image, "has_instances": has_instances},
    )


@staff_member_required
def create_view(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "name is required")
        else:
            image = Image.objects.create(name=name)
            messages.success(request, f"Created Image {image.name}")
            return redirect("ec2_images:detail", pk=image.pk)
    return render(request, "ec2/images/create.html")


@staff_member_required
def update_view(request, pk):
    image = get_object_or_404(Image, pk=pk)
    builds = services.selectable_builds_qs()
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        active_build_id = request.POST.get("active_build") or None
        if not name:
            messages.error(request, "name is required")
        else:
            image.name = name
            image.active_build_id = active_build_id
            image.save()
            messages.success(request, "Updated")
            return redirect("ec2_images:detail", pk=image.pk)
    return render(
        request,
        "ec2/images/update.html",
        {"image": image, "builds": builds},
    )


@staff_member_required
def delete_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_images:detail", pk=pk)
    image = get_object_or_404(Image, pk=pk)
    try:
        services.delete_image(image)
    except services.ImageInUseError as exc:
        messages.error(request, str(exc))
        return redirect("ec2_images:detail", pk=image.pk)
    messages.success(request, "Deleted")
    return redirect("ec2_images:list")
