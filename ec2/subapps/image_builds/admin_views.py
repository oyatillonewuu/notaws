"""Admin-facing views for ImageBuild. Users have no access to this resource —
it is an infrastructure concern, analogous to AWS AMI build pipelines."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render

from ec2.subapps.image_builds.exceptions import (
    BuildInUseError,
    CannotOperateOnDeprecatedBuild,
)
from ec2.subapps.image_builds.schemas import (
    BuildResult,
    HandleDockerfileCodeUpdateResult,
)

from . import services
from .models import ImageBuild

# TODO: fix blocking operations (building/deleting/etc.).


@staff_member_required
def list_view(request):
    builds = ImageBuild.objects.all()
    return render(
        request,
        "ec2/image_builds/list.html",
        {"builds": builds},
    )


@staff_member_required
def detail_view(request, pk):
    build = get_object_or_404(ImageBuild, pk=pk)
    referenced = services.is_referenced(build)
    return render(
        request,
        "ec2/image_builds/detail.html",
        {"build": build, "referenced": referenced},
    )


# TODO: move creation logic to service.
@staff_member_required
def create_view(request):
    if request.method == "POST":
        tag = request.POST.get("tag", "").strip()
        dockerfile_code = request.POST.get("dockerfile_code", "")
        if not tag or not dockerfile_code:
            messages.error(request, "tag and dockerfile_code are required")
        else:
            build = ImageBuild.objects.create(tag=tag, dockerfile_code=dockerfile_code)
            messages.success(request, f"Created ImageBuild {build.tag} (unbuilt)")
            return redirect("ec2_image_builds:detail", pk=build.pk)
    return render(request, "ec2/image_builds/create.html")


@staff_member_required
def update_direct(request, pk):
    build = get_object_or_404(ImageBuild, pk=pk)
    if request.method == "POST":
        tag = request.POST.get("tag", "").strip() or None

        try:
            services.handle_direct_updates(  # type: ignore
                current_build=build,
                tag=tag,
            )
        except Exception as exc:  # docker_ops exceptions surface here
            messages.error(request, f"Update failed: {exc}")
            return redirect("ec2_image_builds:detail", pk=build.pk)

        messages.success(request, "Update successful.")

        return redirect("ec2_image_builds:detail", pk=build.pk)
    return render(request, "ec2/image_builds/update_direct.html", {"build": build})


@staff_member_required
def update_dockerfile_code(request, pk):
    build = get_object_or_404(ImageBuild, pk=pk)

    if request.method == "POST":
        dockerfile_code = request.POST.get("dockerfile_code", "").strip() or None

        try:
            result: HandleDockerfileCodeUpdateResult = (
                services.handle_dockerfile_code_update(  # type: ignore
                    current_build=build,
                    dockerfile_code=dockerfile_code,
                )
            )
        except Exception as exc:  # docker_ops exceptions surface here
            messages.error(request, f"Update failed: {exc}")
            return redirect("ec2_image_builds:detail", pk=build.pk)

        messages.success(request, result.message)

        return redirect("ec2_image_builds:detail", pk=build.pk)
    return render(
        request, "ec2/image_builds/update_dockerfile_code.html", {"build": build}
    )


@staff_member_required
def build_view(request, pk):
    """
    Trigger build or rebuild. Endpoint is the same for both — branches
    on is_built inside services.build().
    """

    if request.method != "POST":
        return redirect("ec2_image_builds:detail", pk=pk)
    build = get_object_or_404(ImageBuild, pk=pk)

    try:
        result: BuildResult = services.build(current_build=build)
    except Exception as exc:
        messages.error(request, f"Build failed: {exc}")
        return redirect("ec2_image_builds:detail", pk=build.pk)

    messages.success(request, message=result.message)

    return redirect("ec2_image_builds:detail", pk=build.pk)


@staff_member_required
def unbuild_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_image_builds:detail", pk=pk)
    build = get_object_or_404(ImageBuild, pk=pk)
    try:
        services.unbuild(current_build=build)
        messages.success(request, "Un-built")
    except (BuildInUseError, CannotOperateOnDeprecatedBuild) as exc:
        messages.error(request, str(exc))
    return redirect("ec2_image_builds:detail", pk=build.pk)


@staff_member_required
def delete_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_image_builds:detail", pk=pk)
    build = get_object_or_404(ImageBuild, pk=pk)
    try:
        services.delete_build(current_build=build)
    except services.BuildInUseError as exc:
        messages.error(request, str(exc))
        return redirect("ec2_image_builds:detail", pk=build.pk)
    messages.success(request, "Deleted")
    return redirect("ec2_image_builds:list")
