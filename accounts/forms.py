from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import User


INSTITUTIONAL_DOMAIN = "@eafit.edu.co"


def clean_institutional_email(value, exclude_pk=None):
    """RF01/RF20: correo institucional y unico, en todos los formularios.

    Lo usan el registro y los formularios de Django Admin. Compara sin
    distinguir mayusculas y tambien contra los nombres de usuario, porque en
    BackToYou el nombre de usuario es el mismo correo.
    """
    email = (value or "").strip().lower()
    if not email.endswith(INSTITUTIONAL_DOMAIN):
        raise ValidationError("Please use an institutional email ending in @eafit.edu.co.")

    taken = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=email))
    if exclude_pk is not None:
        taken = taken.exclude(pk=exclude_pk)
    if taken.exists():
        raise ValidationError("This institutional email is already registered.")

    return email


class EafitAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Institutional email")

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if email is not None and password:
            email = email.strip().lower()
            self.cleaned_data["username"] = email
            username = email

            user = User.objects.filter(email__iexact=email).first()
            if user is not None:
                username = user.get_username()

            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                    params={"username": self.username_field.verbose_name},
                )
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


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
