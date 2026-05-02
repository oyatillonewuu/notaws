import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ec2.subapps.images.models import Image
from ec2.subapps.images.services import selectable_images_for_instance_qs

from . import services
from .exceptions import ImageNotReadyError, InstanceHasNoContainerError
from .models import Instance
from .schemas import CreateResult, DeleteResult, StartResult, StopResult, UpdateResult
from .utils import set_django_message_from_result

logger = logging.getLogger(__name__)


@login_required
def list_view(request):
    instances = Instance.objects.filter(owner=request.user).select_related(
        "image", "image_build_in_use"
    )
    instances_with_status = [
        (inst, services.get_instance_status(instance=inst)) for inst in instances
    ]
    return render(
        request,
        "ec2/instances/list.html",
        {"instances_with_status": instances_with_status},
    )


@login_required
def create_view(request):
    images = selectable_images_for_instance_qs()
    context = {
        "images": images,
        "max_cpu": services.MAX_CPU,
        "max_ram": services.MAX_RAM,
        "max_storage": services.MAX_STORAGE,
        "submitted": {},
    }
    if request.method == "POST":
        name = request.POST.get("name", "").strip() or None
        image_id = request.POST.get("image") or None
        cpu_str = request.POST.get("cpu", "").strip()
        ram_str = request.POST.get("ram", "").strip()
        storage_str = request.POST.get("storage", "").strip()
        context["submitted"] = {
            "name": name or "",
            "image": image_id or "",
            "cpu": cpu_str,
            "ram": ram_str,
            "storage": storage_str,
        }

        errors = []
        if not image_id:
            errors.append("Image is required.")

        cpu = ram = storage = None
        try:
            cpu = int(cpu_str)
            ram = int(ram_str)
            storage = int(storage_str)
        except (ValueError, TypeError):
            errors.append("CPU, RAM, and storage must be whole numbers.")

        if cpu is not None:
            if not (1 <= cpu <= services.MAX_CPU):
                errors.append(f"CPU must be between 1 and {services.MAX_CPU}.")
            if not (1 <= ram <= services.MAX_RAM):
                errors.append(f"RAM must be between 1 and {services.MAX_RAM} GB.")
            if not (1 <= storage <= services.MAX_STORAGE):
                errors.append(f"Storage must be between 1 and {services.MAX_STORAGE} GB.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            image = get_object_or_404(Image, pk=image_id)
            try:
                result: CreateResult = services.create_instance(
                    image=image,
                    ram=ram,
                    cpu=cpu,
                    storage=storage,
                    owner=request.user,
                    name=name,
                )
                set_django_message_from_result(request=request, service_result=result)
                return redirect("ec2_instances:detail", pk=result.instance_pk)
            except ImageNotReadyError as exc:
                messages.error(request, str(exc))
            except Exception:
                logger.exception("create_instance failed for user %s", request.user.pk)
                messages.error(request, "Failed to create instance. Please try again.")

    return render(request, "ec2/instances/create.html", context)


@login_required
def detail_view(request, pk):
    instance = get_object_or_404(Instance, pk=pk, owner=request.user)
    status = services.get_instance_status(instance=instance)
    return render(
        request,
        "ec2/instances/detail.html",
        {"instance": instance, "status": status},
    )


@login_required
def update_view(request, pk):
    instance = get_object_or_404(Instance, pk=pk, owner=request.user)
    context = {
        "instance": instance,
        "max_cpu": services.MAX_CPU,
        "max_ram": services.MAX_RAM,
        "max_storage": services.MAX_STORAGE,
        "submitted": {
            "name": instance.name or "",
            "cpu": str(instance.cpu),
            "ram": str(instance.ram),
            "storage": str(instance.storage),
        },
    }
    if request.method == "POST":
        name = request.POST.get("name", "").strip() or None
        cpu_str = request.POST.get("cpu", "").strip()
        ram_str = request.POST.get("ram", "").strip()
        storage_str = request.POST.get("storage", "").strip()
        context["submitted"] = {
            "name": name or "",
            "cpu": cpu_str,
            "ram": ram_str,
            "storage": storage_str,
        }

        errors = []
        cpu = ram = storage = None
        try:
            cpu = int(cpu_str)
            ram = int(ram_str)
            storage = int(storage_str)
        except (ValueError, TypeError):
            errors.append("CPU, RAM, and storage must be whole numbers.")

        if cpu is not None:
            if not (1 <= cpu <= services.MAX_CPU):
                errors.append(f"CPU must be between 1 and {services.MAX_CPU}.")
            if not (1 <= ram <= services.MAX_RAM):
                errors.append(f"RAM must be between 1 and {services.MAX_RAM} GB.")
            if not (1 <= storage <= services.MAX_STORAGE):
                errors.append(f"Storage must be between 1 and {services.MAX_STORAGE} GB.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            try:
                result: UpdateResult = services.update_instance(
                    instance=instance,
                    name=name,
                    cpu=cpu,
                    ram=ram,
                    storage=storage,
                )
                set_django_message_from_result(request=request, service_result=result)
                return redirect("ec2_instances:detail", pk=instance.pk)
            except Exception:
                logger.exception("update_instance failed for instance %s", instance.pk)
                messages.error(request, "Failed to update instance. Please try again.")

    return render(request, "ec2/instances/update.html", context)


@login_required
def start_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_instances:detail", pk=pk)
    instance = get_object_or_404(Instance, pk=pk, owner=request.user)
    try:
        result: StartResult = services.start_instance(instance=instance)
        set_django_message_from_result(request=request, service_result=result)
    except InstanceHasNoContainerError as exc:
        messages.error(request, str(exc))
    except Exception:
        logger.exception("start_instance failed for instance %s", instance.pk)
        messages.error(request, "Failed to start instance. Please try again.")
    return redirect("ec2_instances:detail", pk=pk)


@login_required
def stop_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_instances:detail", pk=pk)
    instance = get_object_or_404(Instance, pk=pk, owner=request.user)
    try:
        result: StopResult = services.stop_instance(instance=instance)
        set_django_message_from_result(request=request, service_result=result)
    except InstanceHasNoContainerError as exc:
        messages.error(request, str(exc))
    except Exception:
        logger.exception("stop_instance failed for instance %s", instance.pk)
        messages.error(request, "Failed to stop instance. Please try again.")
    return redirect("ec2_instances:detail", pk=pk)


@login_required
def terminal_view(request, pk):
    instance = get_object_or_404(Instance, pk=pk, owner=request.user)
    return render(request, "ec2/instances/terminal.html", {"instance": instance})


@login_required
def delete_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_instances:detail", pk=pk)
    instance = get_object_or_404(Instance, pk=pk, owner=request.user)
    try:
        result: DeleteResult = services.delete_instance(instance=instance)
        set_django_message_from_result(request=request, service_result=result)
    except Exception:
        logger.exception("delete_instance failed for instance %s", instance.pk)
        messages.error(request, "Failed to delete instance. Please try again.")
        return redirect("ec2_instances:detail", pk=pk)
    return redirect("ec2_instances:list")
