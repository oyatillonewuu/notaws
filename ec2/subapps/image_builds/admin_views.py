"""Admin-facing views for ImageBuild. Users have no access to this resource —
it is an infrastructure concern, analogous to AWS AMI build pipelines."""
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from . import services
from .models import ImageBuild


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
def update_view(request, pk):
    build = get_object_or_404(ImageBuild, pk=pk)
    if request.method == "POST":
        tag = request.POST.get("tag", "").strip() or None
        dockerfile_code = request.POST.get("dockerfile_code", None)
        force_rebuild = request.POST.get("force_rebuild") == "on"
        try:
            _, new_build = services.update_build(
                build,
                tag=tag,
                dockerfile_code=dockerfile_code,
                force_rebuild=force_rebuild,
            )
        except Exception as exc:  # docker_ops exceptions surface here
            messages.error(request, f"Update failed: {exc}")
            return redirect("ec2_image_builds:detail", pk=build.pk)
        if new_build is not None:
            messages.success(
                request,
                f"Rebuilt: new build #{new_build.pk} active; #{build.pk} deprecated",
            )
            return redirect("ec2_image_builds:detail", pk=new_build.pk)
        messages.success(request, "Updated")
        return redirect("ec2_image_builds:detail", pk=build.pk)
    return render(request, "ec2/image_builds/update.html", {"build": build})


@staff_member_required
def build_view(request, pk):
    """Trigger build or rebuild. Endpoint is the same for both — branches
    on is_built inside services.build()."""
    if request.method != "POST":
        return redirect("ec2_image_builds:detail", pk=pk)
    build = get_object_or_404(ImageBuild, pk=pk)
    try:
        _, new_build = services.build(build)
    except Exception as exc:
        messages.error(request, f"Build failed: {exc}")
        return redirect("ec2_image_builds:detail", pk=build.pk)
    if new_build is not None:
        messages.success(request, f"Rebuilt; new build #{new_build.pk} is active")
        return redirect("ec2_image_builds:detail", pk=new_build.pk)
    messages.success(request, "Built")
    return redirect("ec2_image_builds:detail", pk=build.pk)


@staff_member_required
def unbuild_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_image_builds:detail", pk=pk)
    build = get_object_or_404(ImageBuild, pk=pk)
    try:
        services.unbuild(build)
        messages.success(request, "Un-built")
    except services.BuildInUseError as exc:
        messages.error(request, str(exc))
    return redirect("ec2_image_builds:detail", pk=build.pk)


@staff_member_required
def delete_view(request, pk):
    if request.method != "POST":
        return redirect("ec2_image_builds:detail", pk=pk)
    build = get_object_or_404(ImageBuild, pk=pk)
    try:
        services.delete_build(build)
    except services.BuildInUseError as exc:
        messages.error(request, str(exc))
        return redirect("ec2_image_builds:detail", pk=build.pk)
    messages.success(request, "Deleted")
    return redirect("ec2_image_builds:list")
