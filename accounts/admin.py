from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.db import transaction

from .forms import clean_institutional_email
from .models import User
from .roles import RoleChangeError, check_account_change, check_account_deletion, record_changes


class BackToYouUserCreationForm(AdminUserCreationForm):
    """Crear cuentas desde Django Admin igual que en el registro: con el
    correo institucional, que tambien queda como nombre de usuario."""

    email = forms.EmailField(label="Institutional email")

    def clean_email(self):
        email = clean_institutional_email(self.cleaned_data.get("email"))
        self.instance.username = email
        return email


class BackToYouUserChangeForm(UserChangeForm):
    """RF20: aplica en Django Admin la misma regla que en la aplicacion."""

    def clean_email(self):
        return clean_institutional_email(
            self.cleaned_data.get("email"),
            exclude_pk=self.instance.pk,
        )

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk is None:
            return cleaned_data

        current = User.objects.get(pk=self.instance.pk)
        new_role = cleaned_data.get("role", current.role)
        new_is_active = cleaned_data.get("is_active", current.is_active)
        try:
            check_account_change(current, new_role, new_is_active)
        except RoleChangeError as error:
            raise ValidationError(str(error))
        return cleaned_data


@admin.register(User)
class BackToYouUserAdmin(UserAdmin):
    form = BackToYouUserChangeForm
    add_form = BackToYouUserCreationForm

    list_display = (
        "username",
        "email",
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    list_filter = (
        "role",
        "is_active",
        "is_staff",
        "is_superuser",
    )
    search_fields = (
        "username",
        "email",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "BackToYou application role",
            {
                "fields": ("role",),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "usable_password", "password1", "password2"),
            },
        ),
        (
            "BackToYou application role",
            {
                "fields": ("role",),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        # El formulario ya valido la regla; aqui se vuelve a comprobar con
        # las filas bloqueadas, por si otro administrador cambio algo entre
        # medio, y se registra quien hizo el cambio y cuando.
        with transaction.atomic():
            previous = User.objects.select_for_update().get(pk=obj.pk) if change else None
            if previous is not None:
                check_account_change(previous, obj.role, obj.is_active, locked=True)
                # Si el nombre de usuario era el correo, sigue al correo nuevo.
                if (
                    previous.username.lower() == previous.email.lower()
                    and obj.username == previous.username
                ):
                    obj.username = obj.email
            record_changes(obj, previous, changed_by=request.user)
            super().save_model(request, obj, form, change)

    def get_deleted_objects(self, objs, request):
        # Si el borrado dejaria la app sin administradores activos, Django
        # muestra la confirmacion como "sin permiso" y no permite borrar.
        # Aplica al boton Delete de una cuenta y a la accion masiva.
        deleted, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        try:
            check_account_deletion(list(objs))
        except RoleChangeError:
            perms_needed = set(perms_needed) | {"the last active administrator account"}
        return deleted, model_count, perms_needed, protected

    def delete_model(self, request, obj):
        with transaction.atomic():
            check_account_deletion([obj])
            super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            check_account_deletion(list(queryset))
            super().delete_queryset(request, queryset)
