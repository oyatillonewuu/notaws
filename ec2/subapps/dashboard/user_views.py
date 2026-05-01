from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import get_dashboard_data


@login_required(login_url="home")
def index_view(request):
    return render(request, "ec2/dashboard/index.html", get_dashboard_data())
