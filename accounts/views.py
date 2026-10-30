from django.contrib import messages
from django.shortcuts import redirect, render

from reports.querysets import flagged_reports

from .decorators import administrator_required
from .forms import EafitUserRegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = EafitUserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Registration successful. You can now log in.")
            return redirect("accounts:login")
    else:
        form = EafitUserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@administrator_required
def administration_panel(request):
    # RF43: el panel avisa cuantos reportes publicados esperan revision.
    return render(
        request,
        "accounts/administration.html",
        {"flagged_report_count": flagged_reports().count()},
    )
