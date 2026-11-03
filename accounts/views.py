from django.contrib import messages
from django.contrib.auth import password_validation
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from reports.querysets import flagged_reports

from .decorators import administrator_required
from .forms import EafitUserRegistrationForm, password_rule_results
from .models import User


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = EafitUserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Registration successful. You can now log in."))
            return redirect("accounts:login")
    else:
        form = EafitUserRegistrationForm()

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            # Las reglas de la contrasena, una por una, para marcarlas con un
            # chulo o una X mientras se escribe (ver password_check).
            "password_rules": password_validation.password_validators_help_texts(),
        },
    )


@require_POST
def password_check(request):
    """Registro: que reglas cumple la contrasena que se lleva escrita.

    La pagina la llama mientras la persona escribe. Usa los mismos datos que
    el formulario (nombre y correo, para la regla de la informacion
    personal), asi que el resultado es el mismo que al enviar. No guarda nada.
    """
    user = User(
        email=request.POST.get("email", "").strip().lower(),
        first_name=request.POST.get("full_name", "").strip(),
    )
    return JsonResponse({"rules": password_rule_results(request.POST.get("password", ""), user)})


@administrator_required
def administration_panel(request):
    # RF43: el panel avisa cuantos reportes publicados esperan revision.
    return render(
        request,
        "accounts/administration.html",
        {"flagged_report_count": flagged_reports().count()},
    )
