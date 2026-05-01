from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.db import OperationalError
from django.shortcuts import redirect, render


class SignupForm(UserCreationForm):
    """Project-local wrapper so templates can refer to a stable form name."""


def home_view(request):
    if request.user.is_authenticated:
        return redirect("welcome")

    login_form = AuthenticationForm(request=request)

    if request.method == "POST":
        login_form = AuthenticationForm(request=request, data=request.POST)
        try:
            if login_form.is_valid():
                login(request, login_form.get_user())
                return redirect("welcome")
        except OperationalError:
            messages.error(
                request,
                "Database is not initialized yet. Run `python manage.py migrate` first.",
            )

    return render(request, "site/home.html", {"login_form": login_form})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("welcome")

    signup_form = SignupForm()

    if request.method == "POST":
        signup_form = SignupForm(request.POST)
        try:
            if signup_form.is_valid():
                user = signup_form.save()
                login(request, user)
                messages.success(request, "Your account has been created.")
                return redirect("welcome")
        except OperationalError:
            messages.error(
                request,
                "Database is not initialized yet. Run `python manage.py migrate` first.",
            )

    return render(request, "site/signup.html", {"signup_form": signup_form})


@login_required(login_url="home")
def welcome_view(request):
    pricing = [
        {
            "name": "Starter",
            "price": "$7/mo",
            "description": "Perfect for trying managed compute images and lightweight workloads.",
            "features": ["1 image pipeline", "Basic monitoring", "Community support"],
        },
        {
            "name": "Growth",
            "price": "$24/mo",
            "description": "Built for teams shipping app images and repeatable infrastructure faster.",
            "features": [
                "5 image pipelines",
                "Live dashboard",
                "Priority email support",
            ],
        },
        {
            "name": "Scale",
            "price": "$79/mo",
            "description": "For larger projects that need predictable deployments and visibility.",
            "features": [
                "Unlimited pipelines",
                "Advanced activity view",
                "Dedicated onboarding",
            ],
        },
    ]
    return render(request, "site/welcome.html", {"pricing": pricing})
