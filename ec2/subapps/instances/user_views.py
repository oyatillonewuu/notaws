"""User-facing views for Instance. Users have full control over their own
instances (per the Access Control table)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ec2.subapps.images.services import selectable_images_for_instance_qs

from . import services
from .models import Instance


def _user_qs(request):
    qs = Instance.objects.select_related("image", "image_build_in_use")
    if request.user.is_staff:
        return qs
    return qs.filter(owner=request.user)


@login_required
def list_view(request):
    instances = _user_qs(request)
    rows = [
        {"obj": i, "status": services.get_status(i)} for i in instances
    ]
    return render(request, "ec2/instances/list.html", {"rows": rows})


@login_required
def create_view(request):
    images = selectable_images_for_instance_qs()
    if request.method == "POST":
        try:
            instance = services.create_instance(
                owner=request.user,
                image=images.get(pk=request.POST["image"]),
                name=request.POST.get("name", "").strip(),
                cpu=int(request.POST.get("cpu", 1)),
                ram=int(request.POST.get("ram", 1)),
                storage=int(request.POST.get("storage", 10)),
            )
        except (services.ResourceLimitError, services.ImageNotReadyError) as exc:
            messages.error(request, str(exc))
        except Exception as exc:
            messages.error(request, f"Create failed: {exc}")
        else:
            messages.success(request, "Instance created")
            return redirect("ec2_instances:detail", pk=instance.pk)
    return render(request, "ec2/instances/create.html", {"images": images})


@login_required
def detail_view(request, pk):
    instance = get_object_or_404(_user_qs(request), pk=pk)
    status = services.get_status(instance)
    return render(
        request,
        "ec2/instances/detail.html",
        {"instance": instance, "status": status},
    )


@login_required
def update_view(request, pk):
    instance = get_object_or_404(_user_qs(request), pk=pk)
    if request.method == "POST":
        try:
            services.update_instance(
                instance,
                name=request.POST.get("name", "").strip(),
                cpu=int(request.POST.get("cpu", instance.cpu)),
                ram=int(request.POST.get("ram", instance.ram)),
                storage=int(request.POST.get("storage", instance.storage)),
            )
        except services.ResourceLimitError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "Updated")
            return redirect("ec2_instances:detail", pk=instance.pk)
    return render(request, "ec2/instances/update.html", {"instance": instance})


@login_required
def start_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_instances:detail", pk=pk)
    instance = get_object_or_404(_user_qs(request), pk=pk)
    try:
        services.start(instance)
        messages.success(request, "Started")
    except Exception as exc:
        messages.error(request, f"Start failed: {exc}")
    return redirect("ec2_instances:detail", pk=instance.pk)


@login_required
def stop_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_instances:detail", pk=pk)
    instance = get_object_or_404(_user_qs(request), pk=pk)
    try:
        services.stop(instance)
        messages.success(request, "Stopped")
    except Exception as exc:
        messages.error(request, f"Stop failed: {exc}")
    return redirect("ec2_instances:detail", pk=instance.pk)


@login_required
def delete_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_instances:detail", pk=pk)
    instance = get_object_or_404(_user_qs(request), pk=pk)
    services.schedule_delete(instance)
    messages.success(request, "Deleted")
    return redirect("ec2_instances:list")


@login_required
def terminal_view(request, pk):
    """Stub per spec — 'Later add terminal attach'."""
    instance = get_object_or_404(_user_qs(request), pk=pk)
    return render(request, "ec2/instances/terminal.html", {"instance": instance})
