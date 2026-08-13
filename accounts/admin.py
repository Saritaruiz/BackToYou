from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class BackToYouUserAdmin(UserAdmin):
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
    add_fieldsets = UserAdmin.add_fieldsets + (
        (
            "BackToYou application role",
            {
                "fields": ("role",),
            },
        ),
    )
