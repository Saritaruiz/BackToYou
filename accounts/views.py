import logging

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from reports.querysets import flagged_reports

from .decorators import administrator_required
from .forms import EafitUserRegistrationForm
from .models import User
from .tokens import account_activation_token


logger = logging.getLogger(__name__)


def _is_waiting_for_activation(user):
    # Inactiva, nunca entro y ningun administrador la desactivo (RF19): es
    # una cuenta que se registro y todavia no abrio el enlace del correo.
    return not user.is_active and user.last_login is None and user.status_changed_by_id is None


def _send_account_email(request, user, template_prefix):
    activation_path = reverse(
        "accounts:activate",
        kwargs={
            "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": account_activation_token.make_token(user),
        },
    )
    context = {
        "user": user,
        "activation_url": request.build_absolute_uri(activation_path),
        "login_url": request.build_absolute_uri(reverse("accounts:login")),
        "password_reset_url": request.build_absolute_uri(reverse("accounts:password_reset")),
    }
    subject = render_to_string(f"accounts/{template_prefix}_subject.txt", context).strip()
    body = render_to_string(f"accounts/{template_prefix}_email.txt", context)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:
        logger.exception("BackToYou account email failed.")


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = EafitUserRegistrationForm(request.POST)
        if form.is_valid():
            # NFR34: la respuesta es la misma tenga o no cuenta el correo. La
            # diferencia solo la ve quien abre ese correo, y la cuenta queda
            # inactiva hasta que lo haga: asi nadie se registra con el correo
            # institucional de otra persona.
            registered = form.registered_user
            if registered is None:
                user = form.save(commit=False)
                user.is_active = False
                user.save()
                _send_account_email(request, user, "activation")
            elif _is_waiting_for_activation(registered):
                # La contrasena nueva reemplaza a la anterior, y con ella
                # vencen los enlaces anteriores: quien se registro primero con
                # un correo ajeno no puede quedarse con la cuenta.
                registered.first_name = form.cleaned_data["full_name"].strip()
                registered.set_password(form.cleaned_data["password1"])
                registered.save()
                _send_account_email(request, registered, "activation")
            else:
                _send_account_email(request, registered, "registration_existing")
            return redirect("accounts:registration_sent")
    else:
        form = EafitUserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def activate_account(request, uidb64, token):
    try:
        user = User.objects.get(pk=urlsafe_base64_decode(uidb64).decode())
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if (
        user is not None
        and _is_waiting_for_activation(user)
        and account_activation_token.check_token(user, token)
    ):
        user.is_active = True
        user.save(update_fields=["is_active"])
        messages.success(request, "Your account is active. You can now log in.")
        return redirect("accounts:login")

    return render(request, "accounts/activation_invalid.html")


@administrator_required
def administration_panel(request):
    # RF43: el panel avisa cuantos reportes publicados esperan revision.
    return render(
        request,
        "accounts/administration.html",
        {"flagged_report_count": flagged_reports().count()},
    )
