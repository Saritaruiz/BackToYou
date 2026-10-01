"""RF20 - la misma regla de cambio de rol en la aplicacion y en Django Admin.

Protege al ultimo administrador activo en todos los caminos (quitar rol,
desactivar, borrar) y registra quien hizo cada cambio y cuando.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import User
from .roles import (
    LAST_ADMIN_DEACTIVATE_MESSAGE,
    LAST_ADMIN_MESSAGE,
    RoleChangeError,
    change_role,
    check_account_deletion,
)


PASSWORD = "StrongPass123"


class RoleRuleTests(TestCase):
    """La regla compartida, sin pasar por ninguna pantalla."""

    def setUp(self):
        Model = get_user_model()
        self.admin = Model.objects.create_user(
            "admin@eafit.edu.co", "admin@eafit.edu.co", PASSWORD, role=User.Role.ADMINISTRATOR
        )
        self.regular = Model.objects.create_user("regular@eafit.edu.co", "regular@eafit.edu.co", PASSWORD)

    def test_change_role_records_who_and_when(self):
        change_role(self.regular, User.Role.ADMINISTRATOR, changed_by=self.admin)

        self.regular.refresh_from_db()
        self.assertEqual(self.regular.role, User.Role.ADMINISTRATOR)
        self.assertEqual(self.regular.role_changed_by, self.admin)
        self.assertIsNotNone(self.regular.role_changed_at)

    def test_change_role_refuses_to_remove_the_last_active_admin(self):
        with self.assertRaisesMessage(RoleChangeError, LAST_ADMIN_MESSAGE):
            change_role(self.admin, User.Role.REGULAR_USER, changed_by=self.admin)

        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMINISTRATOR)

    def test_change_role_uses_the_saved_state_not_a_stale_copy(self):
        # Una copia en memoria vieja no debe saltarse la regla: se cuenta
        # con lo que esta guardado en la base de datos.
        stale_copy = User.objects.get(pk=self.admin.pk)
        other = User.objects.create_user(
            "other@eafit.edu.co", "other@eafit.edu.co", PASSWORD, role=User.Role.ADMINISTRATOR
        )
        change_role(other, User.Role.REGULAR_USER, changed_by=self.admin)

        with self.assertRaises(RoleChangeError):
            change_role(stale_copy, User.Role.REGULAR_USER, changed_by=self.admin)

    def test_deleting_the_last_active_admin_is_refused(self):
        with self.assertRaises(RoleChangeError):
            check_account_deletion([self.admin])

    def test_deleting_a_regular_user_is_allowed(self):
        check_account_deletion([self.regular])


class DjangoAdminRoleRuleTests(TestCase):
    """Django Admin (/admin/) sigue las mismas reglas que la aplicacion."""

    def setUp(self):
        Model = get_user_model()
        # Cuenta tecnica para entrar a /admin/; no cuenta como administrador
        # de BackToYou porque su rol es de usuario regular.
        self.superuser = Model.objects.create_superuser(
            "super@eafit.edu.co", "super@eafit.edu.co", PASSWORD
        )
        self.admin = Model.objects.create_user(
            "admin@eafit.edu.co", "admin@eafit.edu.co", PASSWORD, role=User.Role.ADMINISTRATOR
        )
        self.regular = Model.objects.create_user("regular@eafit.edu.co", "regular@eafit.edu.co", PASSWORD)
        self.client.login(username="super@eafit.edu.co", password=PASSWORD)

    def change_url(self, user):
        return reverse("admin:accounts_user_change", args=[user.pk])

    def form_data(self, user, **changes):
        data = {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "is_active": "on" if user.is_active else "",
            "date_joined_0": user.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": user.date_joined.strftime("%H:%M:%S"),
            "last_login_0": "",
            "last_login_1": "",
            "role": user.role,
        }
        data.update(changes)
        return {key: value for key, value in data.items() if value != ""}

    def test_admin_site_cannot_revoke_the_last_active_admin(self):
        response = self.client.post(
            self.change_url(self.admin),
            self.form_data(self.admin, role=User.Role.REGULAR_USER),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, LAST_ADMIN_MESSAGE)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMINISTRATOR)

    def test_admin_site_cannot_deactivate_the_last_active_admin(self):
        response = self.client.post(
            self.change_url(self.admin),
            self.form_data(self.admin, is_active=""),
        )

        self.assertContains(response, LAST_ADMIN_DEACTIVATE_MESSAGE)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_site_role_change_records_who_and_when(self):
        response = self.client.post(
            self.change_url(self.regular),
            self.form_data(self.regular, role=User.Role.ADMINISTRATOR),
        )

        self.assertEqual(response.status_code, 302)
        self.regular.refresh_from_db()
        self.assertEqual(self.regular.role, User.Role.ADMINISTRATOR)
        self.assertEqual(self.regular.role_changed_by, self.superuser)
        self.assertIsNotNone(self.regular.role_changed_at)

    def test_admin_site_can_revoke_an_admin_when_another_one_remains(self):
        self.client.post(
            self.change_url(self.regular),
            self.form_data(self.regular, role=User.Role.ADMINISTRATOR),
        )

        response = self.client.post(
            self.change_url(self.admin),
            self.form_data(self.admin, role=User.Role.REGULAR_USER),
        )

        self.assertEqual(response.status_code, 302)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.REGULAR_USER)

    def test_admin_site_status_change_records_who_and_when(self):
        response = self.client.post(
            self.change_url(self.regular),
            self.form_data(self.regular, is_active=""),
        )

        self.assertEqual(response.status_code, 302)
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_active)
        self.assertEqual(self.regular.status_changed_by, self.superuser)
        self.assertIsNotNone(self.regular.status_changed_at)

    def test_admin_site_saving_without_changes_does_not_touch_the_audit(self):
        self.client.post(self.change_url(self.regular), self.form_data(self.regular))

        self.regular.refresh_from_db()
        self.assertIsNone(self.regular.role_changed_at)
        self.assertIsNone(self.regular.status_changed_at)

    def test_admin_site_cannot_delete_the_last_active_admin(self):
        url = reverse("admin:accounts_user_delete", args=[self.admin.pk])

        page = self.client.get(url)
        response = self.client.post(url, {"post": "yes"})

        self.assertContains(page, "the last active administrator account")
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertNotEqual(response.status_code, 302)

    def test_admin_site_bulk_delete_cannot_remove_every_active_admin(self):
        url = reverse("admin:accounts_user_changelist")
        selection = {
            "action": "delete_selected",
            "_selected_action": [self.admin.pk, self.regular.pk],
        }

        # Paso 1: la confirmacion explica el motivo y no ofrece borrar.
        confirmation = self.client.post(url, selection)
        # Paso 2: forzar la confirmacion igual es rechazado por Django.
        forced = self.client.post(url, {**selection, "post": "yes"})

        self.assertContains(confirmation, "the last active administrator account")
        self.assertNotContains(confirmation, 'name="post"')
        self.assertEqual(forced.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.regular.pk).exists())

    def test_admin_site_can_delete_a_regular_user(self):
        url = reverse("admin:accounts_user_delete", args=[self.regular.pk])

        response = self.client.post(url, {"post": "yes"})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.regular.pk).exists())
