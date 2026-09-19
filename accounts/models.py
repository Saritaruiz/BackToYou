from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
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
