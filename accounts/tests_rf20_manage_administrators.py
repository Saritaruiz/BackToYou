"""RF20 - Manage Administrator Accounts. Un test por criterio de aceptacion."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import User


class ManageAdministratorAccountsTests(TestCase):
    def setUp(self):
        Model = get_user_model()
        self.admin = Model.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.other_admin = Model.objects.create_user(
            username="otheradmin@eafit.edu.co",
            email="otheradmin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.regular = Model.objects.create_user(
            username="regular@eafit.edu.co",
            email="regular@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.REGULAR_USER,
        )
        self.list_url = reverse("administration_administrator_list")

    def toggle_url(self, user):
        return reverse("administration_administrator_toggle", args=[user.id])

    def login_as(self, user):
        self.client.login(username=user.email, password="StrongPass123")

    # Given an eligible Regular User account, when an authorized
    # Administrator grants Administrator privileges, then the system
    # assigns the Administrator role to that account.
    def test_admin_can_grant_administrator_role_to_a_regular_user(self):
        self.login_as(self.admin)

        response = self.client.post(self.toggle_url(self.regular))

        self.assertRedirects(response, self.list_url)
        self.regular.refresh_from_db()
        self.assertEqual(self.regular.role, User.Role.ADMINISTRATOR)

    # Given an Administrator account, when an authorized Administrator
    # revokes its privileges, then the system changes the account to the
    # Regular User role.
    def test_admin_can_revoke_administrator_role_from_another_admin(self):
        self.login_as(self.admin)

        response = self.client.post(self.toggle_url(self.other_admin))

        self.assertRedirects(response, self.list_url)
        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.role, User.Role.REGULAR_USER)

    # Given the last active Administrator account, when an attempt is made
    # to revoke its Administrator privileges, then the system prevents the
    # action.
    def test_the_last_active_administrator_cannot_be_revoked(self):
        self.other_admin.delete()
        self.login_as(self.admin)

        response = self.client.post(self.toggle_url(self.admin))

        self.assertRedirects(response, self.list_url)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, User.Role.ADMINISTRATOR)

    def test_an_inactive_administrator_can_still_be_revoked_even_if_alone(self):
        # Revocar una cuenta YA inactiva no reduce el numero de
        # administradores activos, asi que no cuenta como "el ultimo".
        self.other_admin.is_active = False
        self.other_admin.save(update_fields=["is_active"])
        self.login_as(self.admin)

        response = self.client.post(self.toggle_url(self.other_admin))

        self.assertRedirects(response, self.list_url)
        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.role, User.Role.REGULAR_USER)

    # Given an account that has just received Administrator privileges,
    # when the user logs in, then the system grants access to the
    # administration panel.
    def test_a_newly_promoted_account_can_access_the_administration_panel(self):
        self.login_as(self.admin)
        self.client.post(self.toggle_url(self.regular))
        self.client.logout()

        self.login_as(self.regular)
        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 200)

    # Given an account whose privileges were just revoked, when the user
    # attempts to open the administration panel, then the system denies
    # access.
    def test_a_newly_revoked_account_loses_access_to_the_administration_panel(self):
        self.login_as(self.admin)
        self.client.post(self.toggle_url(self.other_admin))
        self.client.logout()

        self.login_as(self.other_admin)
        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 403)

    # Given a Regular User, when the user attempts to access the
    # administrator management section, then the system denies access.
    def test_a_regular_user_cannot_access_the_administrator_list(self):
        self.login_as(self.regular)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 403)

    def test_a_regular_user_cannot_toggle_anyones_role(self):
        self.login_as(self.regular)

        response = self.client.post(self.toggle_url(self.other_admin))

        self.assertEqual(response.status_code, 403)
        self.other_admin.refresh_from_db()
        self.assertEqual(self.other_admin.role, User.Role.ADMINISTRATOR)

    def test_an_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    # Given a successful role change, when the system completes the
    # action, then it records the responsible Administrator and the
    # timestamp.
    def test_a_successful_change_records_who_and_when(self):
        self.login_as(self.admin)

        self.client.post(self.toggle_url(self.regular))

        self.regular.refresh_from_db()
        self.assertEqual(self.regular.role_changed_by, self.admin)
        self.assertIsNotNone(self.regular.role_changed_at)

    # Given that the Administrator cancels the confirmation, when the
    # confirmation page closes, then the role of the selected account
    # remains unchanged.
    def test_opening_the_confirmation_page_does_not_change_the_role(self):
        self.login_as(self.admin)

        response = self.client.get(self.toggle_url(self.regular))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.regular.email)
        self.regular.refresh_from_db()
        self.assertEqual(self.regular.role, User.Role.REGULAR_USER)
        self.assertIsNone(self.regular.role_changed_at)

    def test_the_confirmation_page_shows_the_correct_action_per_current_role(self):
        self.login_as(self.admin)

        grant_response = self.client.get(self.toggle_url(self.regular))
        revoke_response = self.client.get(self.toggle_url(self.other_admin))

        self.assertContains(grant_response, "Grant administrator access")
        self.assertContains(revoke_response, "Revoke administrator access")

    def test_the_list_shows_every_account_with_its_current_role(self):
        self.login_as(self.admin)

        response = self.client.get(self.list_url)

        self.assertContains(response, self.admin.email)
        self.assertContains(response, self.other_admin.email)
        self.assertContains(response, self.regular.email)
