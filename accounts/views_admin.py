"""Gestion de cuentas por parte de un administrador.

RF19 Manage User Accounts - RF20 Manage Administrator Accounts
"""

from django.contrib import messages
from django.db import models
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import administrator_required
from .models import User


@administrator_required
def administrator_list(request):
    accounts = get_user_model().objects.all().order_by("email")

    return render(
        request,
        "accounts/administrator_list.html",
        {"accounts": accounts},
    )


@administrator_required
def toggle_administrator(request, user_id):
    target = get_object_or_404(get_user_model(), id=user_id)
    will_be_admin = target.role != User.Role.ADMINISTRATOR

    if request.method == "POST":
        if not will_be_admin and _is_last_active_administrator(target):
            messages.error(
                request,
                "You cannot revoke the last active administrator account.",
            )
            return redirect("administration_administrator_list")

        target.role = (
            User.Role.ADMINISTRATOR if will_be_admin else User.Role.REGULAR_USER
        )
        target.role_changed_by = request.user
        target.role_changed_at = timezone.now()
        target.save(
            update_fields=["role", "role_changed_by", "role_changed_at"]
        )

        messages.success(
            request,
            f"{target.email} is now "
            f"{'an administrator' if will_be_admin else 'a regular user'}.",
        )
        return redirect("administration_administrator_list")

    return render(
        request,
        "accounts/administrator_confirm_toggle.html",
        {"target": target, "will_be_admin": will_be_admin},
    )


def _is_last_active_administrator(user):
    # Revocar una cuenta que ya esta inactiva no reduce el numero de
    # administradores ACTIVOS, asi que nunca es lo que bloquea el ultimo.
    if user.role != User.Role.ADMINISTRATOR or not user.is_active:
        return False

    otros_admins_activos = (
        get_user_model()
        .objects.filter(role=User.Role.ADMINISTRATOR, is_active=True)
        .exclude(id=user.id)
    )
    return not otros_admins_activos.exists()


@administrator_required
def user_list(request):
    accounts = (
        get_user_model()
        .objects.filter(role=User.Role.REGULAR_USER)
        .order_by("email")
    )

    query = request.GET.get("q", "").strip()
    if query:
        accounts = accounts.filter(
            models.Q(email__icontains=query) | models.Q(first_name__icontains=query)
        )

    return render(
        request,
        "accounts/user_list.html",
        {"accounts": accounts, "query": query},
    )


@administrator_required
def toggle_user_status(request, user_id):
    target = get_object_or_404(
        get_user_model(), id=user_id, role=User.Role.REGULAR_USER
    )
    will_be_active = not target.is_active

    if request.method == "POST":
        target.is_active = will_be_active
        target.status_changed_by = request.user
        target.status_changed_at = timezone.now()
        target.save(
            update_fields=["is_active", "status_changed_by", "status_changed_at"]
        )

        messages.success(
            request,
            f"{target.email} is now "
            f"{'active' if will_be_active else 'inactive'}.",
        )
        return redirect("administration_user_list")

    return render(
        request,
        "accounts/user_confirm_toggle.html",
        {"target": target, "will_be_active": will_be_active},
    )
