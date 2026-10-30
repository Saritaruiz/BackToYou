from datetime import timedelta

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from .models import LoginFailure, User


INSTITUTIONAL_DOMAIN = "@eafit.edu.co"

# NFR34: despues de 5 intentos fallidos con el mismo correo, el login se
# bloquea 15 minutos.
LOGIN_MAX_FAILED_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


def clean_institutional_domain(value):
    """RF01: el correo debe ser institucional. Devuelve el correo en minusculas."""
    email = (value or "").strip().lower()
    if not email.endswith(INSTITUTIONAL_DOMAIN):
        raise ValidationError("Please use an institutional email ending in @eafit.edu.co.")
    return email


def find_registered_user(email, exclude_pk=None):
    """La cuenta que ya usa este correo, o None.

    Compara sin distinguir mayusculas y tambien contra los nombres de
    usuario, porque en BackToYou el nombre de usuario es el mismo correo.
    """
    taken = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    return taken.first()


def clean_institutional_email(value, exclude_pk=None):
    """RF01/RF20: correo institucional y unico, en todos los formularios.

    Lo usan el registro y los formularios de Django Admin.
    """
    email = clean_institutional_domain(value)
    if find_registered_user(email, exclude_pk) is not None:
        raise ValidationError("This institutional email is already registered.")
    return email


def _login_is_locked(email):
    since = timezone.now() - timedelta(minutes=LOGIN_LOCKOUT_MINUTES)
    # Los intentos de hace mas de 15 minutos ya no cuentan: se borran para
    # que la tabla no crezca.
    LoginFailure.objects.filter(created_at__lt=since).delete()
    return LoginFailure.objects.filter(email=email).count() >= LOGIN_MAX_FAILED_ATTEMPTS


class EafitAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Institutional email")

    error_messages = {
        **AuthenticationForm.error_messages,
        "too_many_attempts": (
            f"Too many failed attempts. Wait {LOGIN_LOCKOUT_MINUTES} minutes and "
            "try again, or reset your password."
        ),
    }

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if email is not None and password:
            email = email.strip().lower()
            self.cleaned_data["username"] = email
            username = email

            # NFR34: el bloqueo cuenta por correo, exista o no la cuenta, asi
            # que tampoco revela cuales correos estan registrados. Mientras
            # dura, ni la contrasena correcta entra.
            if _login_is_locked(email):
                raise ValidationError(
                    self.error_messages["too_many_attempts"],
                    code="too_many_attempts",
                )

            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                username = user.get_username()

            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                LoginFailure.objects.create(email=email)
                raise ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                    params={"username": self.username_field.verbose_name},
                )
            self.confirm_login_allowed(self.user_cache)
            LoginFailure.objects.filter(email=email).delete()

        return self.cleaned_data


class EafitPasswordResetForm(PasswordResetForm):
    """RF39: pedir el enlace para crear una contrasena nueva.

    Django responde igual exista o no la cuenta, y no envia nada a cuentas
    inactivas; aqui solo se ajusta la etiqueta al correo institucional.
    """

    email = forms.EmailField(
        label="Institutional email",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )


class EafitUserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(max_length=150, label="Full name")
    email = forms.EmailField(label="Institutional email")

    class Meta:
        model = User
        fields = ("full_name", "email", "password1", "password2")

    def clean_email(self):
        return clean_institutional_email(self.cleaned_data["email"])

    role = User.Role.REGULAR_USER

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data["full_name"].strip()
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.role = self.role
        user.first_name = full_name
        if commit:
            user.save()
        return user


class AdministratorCreationForm(EafitUserRegistrationForm):
    """RF20: un administrador crea otra cuenta de administrador desde la app.

    Mismas reglas que el registro (correo institucional unico, contrasena
    segura), pero la cuenta nace con el rol de administrador.
    """

    role = User.Role.ADMINISTRATOR


class AdministratorEditForm(forms.ModelForm):
    """RF20: editar el nombre y el correo de una cuenta de administrador."""

    first_name = forms.CharField(max_length=150, label="Full name")
    email = forms.EmailField(label="Institutional email")

    class Meta:
        model = User
        fields = ("first_name", "email")

    def clean_email(self):
        return clean_institutional_email(self.cleaned_data["email"], exclude_pk=self.instance.pk)

    def save(self, commit=True):
        user = super().save(commit=False)
        # En BackToYou el nombre de usuario es el correo: se mueven juntos.
        if self.initial.get("email", "").lower() == user.username.lower():
            user.username = user.email
        if commit:
            user.save()
        return user
