from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from . import services
from .models import Instance
from .schemas import DeleteResult
from .utils import set_django_message_from_result


@staff_member_required
def list_view(request):
    instances = Instance.objects.select_related(
        "owner", "image", "image_build_in_use"
    ).all()
    return render(request, "ec2/instances/admin_list.html", {"instances": instances})


@staff_member_required
def delete_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_instances:admin:list")
    instance = get_object_or_404(Instance, pk=pk)
    try:
        result: DeleteResult = services.delete_instance(instance=instance)
        set_django_message_from_result(request=request, service_result=result)
    except Exception as exc:
        messages.error(request, f"Delete failed: {exc}")
    return redirect("ec2_instances:admin:list")
