"""Correo institucional y unico en todas las formas de crear o editar cuentas."""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .forms import clean_institutional_email
from .models import User


PASSWORD = "StrongPass123"


class InstitutionalEmailRuleTests(TestCase):
    def setUp(self):
        self.existing = get_user_model().objects.create_user(
            "taken@eafit.edu.co", "taken@eafit.edu.co", PASSWORD
        )

    def test_email_is_normalized_to_lowercase(self):
        self.assertEqual(clean_institutional_email("  New.User@EAFIT.edu.co "), "new.user@eafit.edu.co")

    def test_non_institutional_email_is_rejected(self):
        with self.assertRaisesMessage(Exception, "institutional email ending in @eafit.edu.co"):
            clean_institutional_email("someone@gmail.com")

    def test_repeated_email_is_rejected_ignoring_case(self):
        with self.assertRaisesMessage(Exception, "already registered"):
            clean_institutional_email("TAKEN@eafit.edu.co")

    def test_an_account_can_keep_its_own_email_when_edited(self):
        self.assertEqual(
            clean_institutional_email("taken@eafit.edu.co", exclude_pk=self.existing.pk),
            "taken@eafit.edu.co",
        )

    def test_database_rejects_repeated_email_even_outside_forms(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user("other-name", "Taken@EAFIT.edu.co", PASSWORD)

    def test_accounts_without_email_are_not_blocked_by_the_rule(self):
        get_user_model().objects.create_user("tech-1", "", PASSWORD)
        get_user_model().objects.create_user("tech-2", "", PASSWORD)


class DjangoAdminEmailTests(TestCase):
    def setUp(self):
        Model = get_user_model()
        self.superuser = Model.objects.create_superuser("super@eafit.edu.co", "super@eafit.edu.co", PASSWORD)
        self.taken = Model.objects.create_user("taken@eafit.edu.co", "taken@eafit.edu.co", PASSWORD)
        self.client.login(username="super@eafit.edu.co", password=PASSWORD)

    def add_user(self, email):
        return self.client.post(
            reverse("admin:accounts_user_add"),
            {
                "email": email,
                "first_name": "New",
                "usable_password": "true",
                "password1": "AnotherStrong456",
                "password2": "AnotherStrong456",
                "role": User.Role.REGULAR_USER,
            },
        )

    def change_email(self, user, email):
        return self.client.post(
            reverse("admin:accounts_user_change", args=[user.pk]),
            {
                "username": user.username,
                "first_name": user.first_name,
                "email": email,
                "is_active": "on",
                "date_joined_0": user.date_joined.strftime("%Y-%m-%d"),
                "date_joined_1": user.date_joined.strftime("%H:%M:%S"),
                "role": user.role,
            },
        )

    def test_admin_site_creates_accounts_with_the_email_as_username(self):
        response = self.add_user("New.Person@eafit.edu.co")

        self.assertEqual(response.status_code, 302)
        created = User.objects.get(email="new.person@eafit.edu.co")
        self.assertEqual(created.username, "new.person@eafit.edu.co")

    def test_created_account_can_log_in_to_the_app(self):
        self.add_user("new.person@eafit.edu.co")
        self.client.logout()

        logged_in = self.client.login(username="new.person@eafit.edu.co", password="AnotherStrong456")

        self.assertTrue(logged_in)

    def test_admin_site_rejects_non_institutional_email_on_create(self):
        response = self.add_user("someone@gmail.com")

        self.assertContains(response, "institutional email ending in @eafit.edu.co")
        self.assertFalse(User.objects.filter(email="someone@gmail.com").exists())

    def test_admin_site_rejects_repeated_email_on_create(self):
        response = self.add_user("TAKEN@eafit.edu.co")

        self.assertContains(response, "already registered")
        self.assertEqual(User.objects.filter(email__iexact="taken@eafit.edu.co").count(), 1)

    def test_admin_site_rejects_repeated_email_on_edit(self):
        other = get_user_model().objects.create_user("other@eafit.edu.co", "other@eafit.edu.co", PASSWORD)

        response = self.change_email(other, "taken@eafit.edu.co")

        self.assertContains(response, "already registered")
        other.refresh_from_db()
        self.assertEqual(other.email, "other@eafit.edu.co")

    def test_admin_site_rejects_non_institutional_email_on_edit(self):
        response = self.change_email(self.taken, "taken@gmail.com")

        self.assertContains(response, "institutional email ending in @eafit.edu.co")

    def test_admin_site_edit_keeps_username_in_sync_with_the_new_email(self):
        response = self.change_email(self.taken, "renamed@eafit.edu.co")

        self.assertEqual(response.status_code, 302)
        self.taken.refresh_from_db()
        self.assertEqual(self.taken.email, "renamed@eafit.edu.co")
        self.assertEqual(self.taken.username, "renamed@eafit.edu.co")

    def test_admin_site_edit_can_save_an_account_with_its_own_email(self):
        response = self.change_email(self.taken, "taken@eafit.edu.co")

        self.assertEqual(response.status_code, 302)
