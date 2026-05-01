from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required(login_url="home")
def index_view(request):
    return redirect("ec2_dashboard:index")
