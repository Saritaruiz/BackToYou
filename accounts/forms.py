from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError

from .models import User


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
        email = self.cleaned_data["email"].strip().lower()
        if not email.endswith("@eafit.edu.co"):
            raise forms.ValidationError(
                "Please use an institutional email ending in @eafit.edu.co."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This institutional email is already registered.")
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("This institutional email is already registered.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data["full_name"].strip()
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.role = User.Role.REGULAR_USER
        user.first_name = full_name
        if commit:
            user.save()
        return user
