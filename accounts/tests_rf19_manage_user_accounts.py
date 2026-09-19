"""RF19 - Manage User Accounts. Un test por criterio de aceptacion."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from reports.models import Category, ItemReport
from .models import User


class ManageUserAccountsTests(TestCase):
    def setUp(self):
        Model = get_user_model()
        self.admin = Model.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.regular = Model.objects.create_user(
            username="regular@eafit.edu.co",
            email="regular@eafit.edu.co",
            password="StrongPass123",
            first_name="Regular Person",
            role=User.Role.REGULAR_USER,
        )
        self.other_admin = Model.objects.create_user(
            username="otheradmin@eafit.edu.co",
            email="otheradmin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.list_url = reverse("administration_user_list")

    def toggle_url(self, user):
        return reverse("administration_user_toggle", args=[user.id])

    def login_as(self, user):
        return self.client.login(username=user.email, password="StrongPass123")

    # Given an active Regular User account, when the Administrator confirms
    # its deactivation, then the system changes the account status to
    # inactive.
    def test_admin_can_deactivate_an_active_regular_user(self):
        self.login_as(self.admin)

        response = self.client.post(self.toggle_url(self.regular))

        self.assertRedirects(response, self.list_url)
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_active)

    # Given an inactive Regular User account, when the Administrator
    # confirms its activation, then the system changes the account status
    # to active.
    def test_admin_can_activate_an_inactive_regular_user(self):
        self.regular.is_active = False
        self.regular.save(update_fields=["is_active"])
        self.login_as(self.admin)

        response = self.client.post(self.toggle_url(self.regular))

        self.assertRedirects(response, self.list_url)
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_active)

    # Given an inactive account, when the user attempts to log in, then the
    # system denies access.
    def test_an_inactive_account_cannot_log_in(self):
        self.regular.is_active = False
        self.regular.save(update_fields=["is_active"])

        logged_in = self.login_as(self.regular)

        self.assertFalse(logged_in)

    # Given a reactivated account and valid credentials, when the user logs
    # in, then the system grants access to the Regular User functions.
    def test_a_reactivated_account_can_log_in_and_use_the_app(self):
        self.regular.is_active = False
        self.regular.save(update_fields=["is_active"])
        self.regular.is_active = True
        self.regular.save(update_fields=["is_active"])

        logged_in = self.login_as(self.regular)
        response = self.client.get(reverse("reports:my_reports"))

        self.assertTrue(logged_in)
        self.assertEqual(response.status_code, 200)

    # Given a deactivated account, when its existing session is used, then
    # the system denies access to authenticated functions.
    def test_deactivating_an_account_closes_its_existing_session(self):
        self.login_as(self.regular)
        # Confirma que la sesion funciona antes de desactivar la cuenta.
        self.assertEqual(self.client.get(reverse("reports:my_reports")).status_code, 200)

        self.regular.is_active = False
        self.regular.save(update_fields=["is_active"])

        response = self.client.get(reverse("reports:my_reports"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    # Given a search by name or institutional email, when the
    # Administrator submits it, then the system displays the matching
    # accounts.
    def test_searching_by_email_returns_matching_accounts(self):
        other = get_user_model().objects.create_user(
            username="other@eafit.edu.co",
            email="other@eafit.edu.co",
            password="StrongPass123",
            first_name="Other Person",
            role=User.Role.REGULAR_USER,
        )
        self.login_as(self.admin)

        response = self.client.get(self.list_url, {"q": "regular@eafit"})

        self.assertContains(response, self.regular.email)
        self.assertNotContains(response, other.email)

    def test_searching_by_name_returns_matching_accounts(self):
        self.login_as(self.admin)

        response = self.client.get(self.list_url, {"q": "Regular Person"})

        self.assertContains(response, self.regular.email)

    # Given a Regular User, when the user attempts to access the user
    # management section, then the system denies access.
    def test_a_regular_user_cannot_access_the_user_list(self):
        self.login_as(self.regular)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 403)

    def test_a_regular_user_cannot_toggle_anyones_status(self):
        target = get_user_model().objects.create_user(
            username="target@eafit.edu.co",
            email="target@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.REGULAR_USER,
        )
        self.login_as(self.regular)

        response = self.client.post(self.toggle_url(target))

        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertTrue(target.is_active)

    def test_an_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    # Given an administrative account status change, when the system
    # completes the action, then it records the responsible Administrator
    # and the timestamp.
    def test_a_successful_change_records_who_and_when(self):
        self.login_as(self.admin)

        self.client.post(self.toggle_url(self.regular))

        self.regular.refresh_from_db()
        self.assertEqual(self.regular.status_changed_by, self.admin)
        self.assertIsNotNone(self.regular.status_changed_at)

    # Given that the Administrator cancels the confirmation, when the
    # confirmation page closes, then the user account remains unchanged.
    def test_opening_the_confirmation_page_does_not_change_the_status(self):
        self.login_as(self.admin)

        response = self.client.get(self.toggle_url(self.regular))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.regular.email)
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_active)
        self.assertIsNone(self.regular.status_changed_at)

    # Given the reports created by a deactivated user, when the account is
    # deactivated, then those reports keep their current status and remain
    # associated with their creator.
    def test_deactivating_a_user_does_not_touch_their_reports(self):
        category = Category.objects.create(name="Electronics")
        report = ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=category,
            event_date="2026-08-10",
            location="Library",
            creator=self.regular,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )
        self.login_as(self.admin)

        self.client.post(self.toggle_url(self.regular))

        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.ACTIVE)
        self.assertEqual(report.creator, self.regular)

    # El listado es solo de usuarios regulares: administrar el rol de un
    # administrador es responsabilidad de RF20, no de esta pantalla.
    def test_the_list_only_shows_regular_users_not_administrators(self):
        self.login_as(self.admin)

        response = self.client.get(self.list_url)

        self.assertContains(response, self.regular.email)
        self.assertNotContains(response, self.admin.email)
        self.assertNotContains(response, self.other_admin.email)

    def test_an_administrator_account_cannot_be_toggled_through_this_endpoint(self):
        self.login_as(self.admin)

        response = self.client.post(self.toggle_url(self.other_admin))

        self.assertEqual(response.status_code, 404)
        self.other_admin.refresh_from_db()
        self.assertTrue(self.other_admin.is_active)
