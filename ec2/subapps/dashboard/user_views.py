from django.shortcuts import render


def home_view(request):
    return render(request, "ec2/dashboard/home.html")
