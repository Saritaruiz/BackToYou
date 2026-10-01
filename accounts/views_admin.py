"""Gestion de cuentas por parte de un administrador.

RF19 Manage User Accounts - RF20 Manage Administrator Accounts
"""

from django.contrib import messages
from django.contrib.auth import get_user_model, logout
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import administrator_required
from .forms import AdministratorCreationForm, AdministratorEditForm
from .models import User
from .roles import RoleChangeError, change_role, change_status, record_changes


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
        new_role = User.Role.ADMINISTRATOR if will_be_admin else User.Role.REGULAR_USER
        try:
            change_role(target, new_role, changed_by=request.user)
        except RoleChangeError as error:
            messages.error(request, str(error))
            return redirect("administration_administrator_list")

        # Quien se quita el rol a si mismo ya no puede ver la lista de
        # administradores: se le envia al inicio en vez de mostrarle un 403.
        if target == request.user and not will_be_admin:
            messages.success(
                request,
                "You are no longer an administrator. "
                "Your account now has regular user access.",
            )
            return redirect("home")

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


@administrator_required
def administrator_create(request):
    if request.method == "POST":
        form = AdministratorCreationForm(request.POST)
        if form.is_valid():
            account = form.save(commit=False)
            record_changes(account, None, changed_by=request.user)
            account.save()
            messages.success(request, f"{account.email} was created as an administrator.")
            return redirect("administration_administrator_list")
    else:
        form = AdministratorCreationForm()

    return render(
        request,
        "accounts/administrator_form.html",
        {"form": form, "is_new": True},
    )


@administrator_required
def administrator_edit(request, user_id):
    target = get_object_or_404(
        get_user_model(), id=user_id, role=User.Role.ADMINISTRATOR
    )

    if request.method == "POST":
        form = AdministratorEditForm(request.POST, instance=target)
        if form.is_valid():
            form.save()
            messages.success(request, f"{target.email} was updated.")
            return redirect("administration_administrator_list")
    else:
        form = AdministratorEditForm(instance=target)

    return render(
        request,
        "accounts/administrator_form.html",
        {"form": form, "is_new": False, "target": target},
    )


@administrator_required
def toggle_administrator_status(request, user_id):
    target = get_object_or_404(
        get_user_model(), id=user_id, role=User.Role.ADMINISTRATOR
    )
    will_be_active = not target.is_active

    if request.method == "POST":
        try:
            change_status(target, will_be_active, changed_by=request.user)
        except RoleChangeError as error:
            messages.error(request, str(error))
            return redirect("administration_administrator_list")

        # Quien se desactiva a si mismo pierde el acceso en ese momento.
        if target == request.user:
            logout(request)
            messages.success(request, "Your administrator account is now inactive.")
            return redirect("accounts:login")

        messages.success(
            request,
            f"{target.email} is now {'active' if will_be_active else 'inactive'}.",
        )
        return redirect("administration_administrator_list")

    return render(
        request,
        "accounts/administrator_confirm_status.html",
        {"target": target, "will_be_active": will_be_active},
    )


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
