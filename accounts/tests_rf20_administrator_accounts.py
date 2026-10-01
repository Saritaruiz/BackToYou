"""RF20 - crear, editar y desactivar cuentas de administrador desde la app."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import User
from .roles import LAST_ADMIN_DEACTIVATE_MESSAGE


PASSWORD = "StrongPass123"


class AdministratorAccountsTests(TestCase):
    def setUp(self):
        Model = get_user_model()
        self.admin = Model.objects.create_user(
            "admin@eafit.edu.co", "admin@eafit.edu.co", PASSWORD,
            first_name="Ana Admin", role=User.Role.ADMINISTRATOR,
        )
        self.other_admin = Model.objects.create_user(
            "other@eafit.edu.co", "other@eafit.edu.co", PASSWORD,
            first_name="Otto Admin", role=User.Role.ADMINISTRATOR,
        )
        self.regular = Model.objects.create_user(
            "regular@eafit.edu.co", "regular@eafit.edu.co", PASSWORD, first_name="Rita",
        )
        self.client.login(username=self.admin.email, password=PASSWORD)

    def create_admin(self, email="new.admin@eafit.edu.co"):
        return self.client.post(
            reverse("administration_administrator_create"),
            {
                "full_name": "New Admin",
                "email": email,
                "password1": "AnotherStrong456",
                "password2": "AnotherStrong456",
            },
        )

    def edit(self, user, **data):
        return self.client.post(reverse("administration_administrator_edit", args=[user.pk]), data)

    def status_url(self, user):
        return reverse("administration_administrator_status", args=[user.pk])

    # --- Crear -----------------------------------------------------------

    def test_admin_creates_an_administrator_account(self):
        response = self.create_admin()

        self.assertRedirects(response, reverse("administration_administrator_list"))
        created = User.objects.get(email="new.admin@eafit.edu.co")
        self.assertEqual(created.role, User.Role.ADMINISTRATOR)
        self.assertEqual(created.username, "new.admin@eafit.edu.co")
        self.assertEqual(created.first_name, "New Admin")
        self.assertEqual(created.role_changed_by, self.admin)
        self.assertIsNotNone(created.role_changed_at)

    def test_new_administrator_can_log_in_and_open_the_panel(self):
        self.create_admin()
        self.client.logout()

        self.client.login(username="new.admin@eafit.edu.co", password="AnotherStrong456")
        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 200)

    def test_create_rejects_non_institutional_email(self):
        response = self.create_admin("new.admin@gmail.com")

        self.assertContains(response, "institutional email ending in @eafit.edu.co")
        self.assertFalse(User.objects.filter(email="new.admin@gmail.com").exists())

    def test_create_rejects_an_email_already_in_use(self):
        response = self.create_admin("REGULAR@eafit.edu.co")

        self.assertContains(response, "already registered")
        self.regular.refresh_from_db()
        self.assertEqual(self.regular.role, User.Role.REGULAR_USER)

    # --- Editar ----------------------------------------------------------

    def test_admin_edits_name_and_email_of_an_administrator(self):
        response = self.edit(self.other_admin, first_name="Otto Renamed", email="Otto.New@eafit.edu.co")

        self.assertRedirects(response, reverse("administration_administrator_list"))
        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.first_name, "Otto Renamed")
        self.assertEqual(self.other_admin.email, "otto.new@eafit.edu.co")
        self.assertEqual(self.other_admin.username, "otto.new@eafit.edu.co")

    def test_edited_administrator_logs_in_with_the_new_email(self):
        self.edit(self.other_admin, first_name="Otto", email="otto.new@eafit.edu.co")
        self.client.logout()

        self.assertTrue(self.client.login(username="otto.new@eafit.edu.co", password=PASSWORD))

    def test_edit_rejects_an_email_already_in_use(self):
        response = self.edit(self.other_admin, first_name="Otto", email="regular@eafit.edu.co")

        self.assertContains(response, "already registered")
        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.email, "other@eafit.edu.co")

    def test_edit_rejects_an_empty_name(self):
        response = self.edit(self.other_admin, first_name="   ", email="other@eafit.edu.co")

        self.assertContains(response, "This field is required.")
        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.first_name, "Otto Admin")

    def test_edit_page_is_only_for_administrator_accounts(self):
        response = self.client.get(reverse("administration_administrator_edit", args=[self.regular.pk]))

        self.assertEqual(response.status_code, 404)

    # --- Desactivar y activar ----------------------------------------------

    def test_admin_deactivates_another_administrator(self):
        response = self.client.post(self.status_url(self.other_admin))

        self.assertRedirects(response, reverse("administration_administrator_list"))
        self.other_admin.refresh_from_db()
        self.assertFalse(self.other_admin.is_active)
        self.assertEqual(self.other_admin.role, User.Role.ADMINISTRATOR)
        self.assertEqual(self.other_admin.status_changed_by, self.admin)
        self.assertIsNotNone(self.other_admin.status_changed_at)

    def test_deactivated_administrator_cannot_log_in(self):
        self.client.post(self.status_url(self.other_admin))
        self.client.logout()

        self.assertFalse(self.client.login(username=self.other_admin.email, password=PASSWORD))

    def test_admin_reactivates_an_inactive_administrator(self):
        self.client.post(self.status_url(self.other_admin))

        self.client.post(self.status_url(self.other_admin))

        self.other_admin.refresh_from_db()
        self.assertTrue(self.other_admin.is_active)

    def test_the_last_active_administrator_cannot_be_deactivated(self):
        self.other_admin.delete()

        response = self.client.post(self.status_url(self.admin), follow=True)

        self.assertContains(response, LAST_ADMIN_DEACTIVATE_MESSAGE)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_who_deactivates_themselves_is_logged_out(self):
        response = self.client.post(self.status_url(self.admin), follow=True)

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertContains(response, "Your administrator account is now inactive.")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_opening_the_confirmation_does_not_change_the_status(self):
        response = self.client.get(self.status_url(self.other_admin))

        self.assertContains(response, "Deactivate Administrator")
        self.other_admin.refresh_from_db()
        self.assertTrue(self.other_admin.is_active)

    # --- Acceso ------------------------------------------------------------

    def test_regular_users_cannot_use_any_of_these_pages(self):
        self.client.logout()
        self.client.login(username=self.regular.email, password=PASSWORD)

        for url in (
            reverse("administration_administrator_create"),
            reverse("administration_administrator_edit", args=[self.admin.pk]),
            self.status_url(self.admin),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url).status_code, 403)

    def test_list_offers_create_edit_and_status_actions(self):
        response = self.client.get(reverse("administration_administrator_list"))

        self.assertContains(response, reverse("administration_administrator_create"))
        self.assertContains(response, reverse("administration_administrator_edit", args=[self.other_admin.pk]))
        self.assertContains(response, self.status_url(self.other_admin))
        self.assertNotContains(response, reverse("administration_administrator_edit", args=[self.regular.pk]))
