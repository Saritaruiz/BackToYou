"""RF20 - reglas de cambio de rol y de estado de las cuentas.

Un solo lugar para lo que protege al ultimo administrador activo y para
registrar quien hizo cada cambio. Lo usan la aplicacion (views_admin.py) y
Django Admin (admin.py), para que las dos sigan exactamente las mismas reglas.
"""

from django.db import transaction
from django.utils import timezone

from .models import User


LAST_ADMIN_MESSAGE = "You cannot revoke the last active administrator account."
LAST_ADMIN_DEACTIVATE_MESSAGE = "You cannot deactivate the last active administrator account."
LAST_ADMIN_DELETE_MESSAGE = "You cannot delete the last active administrator account."


class RoleChangeError(Exception):
    """Cambio rechazado; el mensaje se puede mostrar tal cual."""


def _counts_as_active_admin(role, is_active):
    return role == User.Role.ADMINISTRATOR and is_active


def _other_active_admins(user, locked=False):
    others = User.objects.filter(role=User.Role.ADMINISTRATOR, is_active=True)
    if user.pk:
        others = others.exclude(pk=user.pk)
    if locked:
        # Bloquea las filas de los demas administradores hasta terminar la
        # transaccion: si dos administradores se quitan el rol a la vez, el
        # segundo espera y vuelve a contar, en vez de dejar la app sin ninguno.
        others = others.select_for_update()
    return others


def check_account_change(user, new_role, new_is_active, locked=False):
    """Lanza RoleChangeError si el cambio dejaria la app sin administradores activos.

    `user` debe tener el estado ACTUAL guardado en la base de datos.
    """
    was_active_admin = _counts_as_active_admin(user.role, user.is_active)
    stays_active_admin = _counts_as_active_admin(new_role, new_is_active)

    if not was_active_admin or stays_active_admin:
        return

    if _other_active_admins(user, locked=locked).exists():
        return

    if new_role != User.Role.ADMINISTRATOR:
        raise RoleChangeError(LAST_ADMIN_MESSAGE)
    raise RoleChangeError(LAST_ADMIN_DEACTIVATE_MESSAGE)


def check_account_deletion(users):
    """Lanza RoleChangeError si borrar `users` deja la app sin administradores activos."""
    ids = [user.pk for user in users]
    deletes_an_active_admin = any(
        _counts_as_active_admin(user.role, user.is_active) for user in users
    )
    if not deletes_an_active_admin:
        return

    survivors = User.objects.filter(
        role=User.Role.ADMINISTRATOR, is_active=True
    ).exclude(pk__in=ids)
    if not survivors.exists():
        raise RoleChangeError(LAST_ADMIN_DELETE_MESSAGE)


def record_changes(user, previous, changed_by):
    """Anota quien y cuando cambio el rol y/o el estado respecto a `previous`.

    Devuelve los nombres de campo modificados, para usarlos en update_fields.
    """
    now = timezone.now()
    fields = []
    # Una cuenta nueva solo registra cambio de rol si nace administradora.
    role_changed = (
        user.role == User.Role.ADMINISTRATOR
        if previous is None
        else previous.role != user.role
    )
    if role_changed:
        user.role_changed_by = changed_by
        user.role_changed_at = now
        fields += ["role_changed_by", "role_changed_at"]
    if previous is not None and previous.is_active != user.is_active:
        user.status_changed_by = changed_by
        user.status_changed_at = now
        fields += ["status_changed_by", "status_changed_at"]
    return fields


def change_status(target, new_is_active, changed_by):
    """Activa o desactiva `target` aplicando las reglas del RF20."""
    with transaction.atomic():
        current = User.objects.select_for_update().get(pk=target.pk)
        check_account_change(current, current.role, new_is_active, locked=True)

        target.is_active = new_is_active
        target.status_changed_by = changed_by
        target.status_changed_at = timezone.now()
        target.save(update_fields=["is_active", "status_changed_by", "status_changed_at"])


def change_role(target, new_role, changed_by):
    """Cambia el rol de `target` aplicando las reglas del RF20."""
    with transaction.atomic():
        current = User.objects.select_for_update().get(pk=target.pk)
        check_account_change(current, new_role, current.is_active, locked=True)

        target.role = new_role
        target.role_changed_by = changed_by
        target.role_changed_at = timezone.now()
        target.save(update_fields=["role", "role_changed_by", "role_changed_at"])
