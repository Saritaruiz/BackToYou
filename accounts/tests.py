from django.contrib.auth import get_user_model
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .admin import BackToYouUserAdmin
from .views import administration_panel
from .models import User


class RegistrationLoginTests(TestCase):
    def test_registration_requires_eafit_email(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Test User",
                "email": "test@example.com",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "@eafit.edu.co")
        self.assertFalse(get_user_model().objects.exists())

    def test_registration_creates_regular_user_with_hashed_password(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Test User",
                "email": "testuser@eafit.edu.co",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )

        self.assertRedirects(response, reverse("accounts:login"))
        user = get_user_model().objects.get(email="testuser@eafit.edu.co")
        self.assertEqual(user.role, User.Role.REGULAR_USER)
        self.assertNotEqual(user.password, "StrongPass123")
        self.assertTrue(user.check_password("StrongPass123"))

    def test_duplicate_institutional_email_is_rejected(self):
        get_user_model().objects.create_user(
            username="testuser@eafit.edu.co",
            email="testuser@eafit.edu.co",
            password="StrongPass123",
        )

        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "Other User",
                "email": "TESTUSER@eafit.edu.co",
                "password1": "StrongPass123",
                "password2": "StrongPass123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already registered")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_login_logout_and_inactive_user_denial(self):
        user = get_user_model().objects.create_user(
            username="active@eafit.edu.co",
            email="active@eafit.edu.co",
            password="StrongPass123",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"username": user.email, "password": "StrongPass123"},
        )
        self.assertRedirects(response, reverse("home"))

        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("home"))

        user.is_active = False
        user.save()
        response = self.client.post(
            reverse("accounts:login"),
            {"username": user.email, "password": "StrongPass123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Please enter a correct")

    def test_existing_user_with_email_username_mismatch_can_login_with_email(self):
        user = get_user_model().objects.create_user(
            username="legacy-user",
            email="legacy@eafit.edu.co",
            password="StrongPass123",
        )

        response = self.client.post(
            reverse("accounts:login"),
            {"username": user.email, "password": "StrongPass123"},
        )

        self.assertRedirects(response, reverse("home"))


class AdministrationPanelTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.regular_user = UserModel.objects.create_user(
            username="regular@eafit.edu.co",
            email="regular@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.REGULAR_USER,
        )
        self.admin_user = UserModel.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )

    def test_anonymous_user_cannot_access_administration_panel(self):
        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_regular_user_receives_403(self):
        self.client.login(
            username=self.regular_user.email,
            password="StrongPass123",
        )

        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 403)

    def test_administrator_can_access_panel(self):
        self.assertFalse(self.admin_user.is_staff)
        self.assertFalse(self.admin_user.is_superuser)

        self.client.login(
            username=self.admin_user.email,
            password="StrongPass123",
        )

        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "BackToYou Administration")
        self.assertContains(response, "Pending Reports / Report Moderation")
        self.assertContains(response, "Categories")
        self.assertContains(response, "User Management")

    def test_administrator_role_does_not_require_staff_or_superuser_flags(self):
        self.admin_user.is_staff = False
        self.admin_user.is_superuser = False
        self.admin_user.save()

        self.client.login(
            username=self.admin_user.email,
            password="StrongPass123",
        )

        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 200)

    def test_inactive_administrator_cannot_access_panel(self):
        self.admin_user.is_active = False
        self.admin_user.save()
        request = RequestFactory().get(reverse("administration"))
        request.user = self.admin_user

        with self.assertRaises(PermissionDenied):
            administration_panel(request)

    def test_administration_navigation_link_is_visible_to_administrator(self):
        self.client.login(
            username=self.admin_user.email,
            password="StrongPass123",
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, "Administration")
        self.assertContains(response, reverse("administration"))

    def test_administration_navigation_link_is_hidden_from_regular_user(self):
        self.client.login(
            username=self.regular_user.email,
            password="StrongPass123",
        )

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Administration")
        self.assertNotContains(response, reverse("administration"))


class UserAdminRoleManagementTests(TestCase):
    def setUp(self):
        self.user_admin = admin.site._registry[User]

    def test_user_admin_uses_backtoyou_configuration(self):
        self.assertIsInstance(self.user_admin, BackToYouUserAdmin)

    def test_user_admin_list_displays_role_and_django_flags(self):
        self.assertEqual(
            self.user_admin.list_display,
            (
                "username",
                "email",
                "role",
                "is_active",
                "is_staff",
                "is_superuser",
            ),
        )

    def test_user_admin_filters_and_search_include_role_fields(self):
        self.assertIn("role", self.user_admin.list_filter)
        self.assertIn("is_active", self.user_admin.list_filter)
        self.assertIn("is_staff", self.user_admin.list_filter)
        self.assertIn("is_superuser", self.user_admin.list_filter)
        self.assertIn("username", self.user_admin.search_fields)
        self.assertIn("email", self.user_admin.search_fields)

    def test_user_admin_edit_and_creation_forms_include_role(self):
        edit_fields = [
            field
            for _, options in self.user_admin.fieldsets
            for field in options["fields"]
        ]
        creation_fields = [
            field
            for _, options in self.user_admin.add_fieldsets
            for field in options["fields"]
        ]

        self.assertIn("role", edit_fields)
        self.assertIn("role", creation_fields)
