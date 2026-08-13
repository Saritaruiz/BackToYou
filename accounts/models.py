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
    