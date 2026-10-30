from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    class Meta(AbstractUser.Meta):
        constraints = [
            # Un correo no se puede repetir, aunque cambien las mayusculas.
            # Protege tambien lo que no pasa por formularios (consola, scripts).
            # Las cuentas sin correo quedan fuera de la regla.
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="unique_user_email_case_insensitive",
            ),
        ]

    class Role(models.TextChoices):
        REGULAR_USER = "REGULAR_USER", "Regular User"
        ADMINISTRATOR = "ADMINISTRATOR", "Administrator"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REGULAR_USER,
    )

    # RF20: quien cambio el rol de esta cuenta por ultima vez, y cuando.
    # Mismo patron que ItemReport.moderated_by/moderated_at.
    role_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="role_changes_made",
        blank=True,
        null=True,
    )

    role_changed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    # RF19: igual que role_changed_by/at, pero para activar/desactivar
    # cuentas de usuario regular. Se mantienen separados de los campos de
    # rol para no mezclar dos auditorias distintas en las mismas columnas.
    status_changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="status_changes_made",
        blank=True,
        null=True,
    )

    status_changed_at = models.DateTimeField(
        blank=True,
        null=True,
    )


# NFR34: intento fallido de iniciar sesion. Sirve para frenar a quien prueba
# contrasenas una tras otra (ver EafitAuthenticationForm). Se guarda el correo
# escrito, exista o no la cuenta, y los intentos viejos se borran solos.
class LoginFailure(models.Model):
    email = models.CharField(max_length=254, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self):
        return f"Failed login for {self.email}"
