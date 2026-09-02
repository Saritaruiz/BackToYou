"""RF14 - Manage Categories."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Category, ItemReport


class ManageCategoriesTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.admin_user = UserModel.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.regular_user = UserModel.objects.create_user(
            username="regular@eafit.edu.co",
            email="regular@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.REGULAR_USER,
        )
        self.creator = UserModel.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")

    def login_as_admin(self):
        self.client.login(username=self.admin_user.email, password="StrongPass123")

    def login_as_regular_user(self):
        self.client.login(username=self.regular_user.email, password="StrongPass123")

    def test_anonymous_user_cannot_access_category_management(self):
        response = self.client.get(reverse("administration_category_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_regular_user_receives_403(self):
        self.login_as_regular_user()

        response = self.client.get(reverse("administration_category_list"))

        self.assertEqual(response.status_code, 403)

    def test_administrator_can_list_categories(self):
        self.login_as_admin()

        response = self.client.get(reverse("administration_category_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Electronics")
        self.assertContains(response, reverse("administration_category_create"))
        self.assertContains(
            response,
            reverse("administration_category_edit", args=[self.category.id]),
        )
        self.assertContains(
            response,
            reverse("administration_category_delete", args=[self.category.id]),
        )

    def test_administration_panel_links_to_category_management(self):
        self.login_as_admin()

        response = self.client.get(reverse("administration"))

        self.assertContains(response, reverse("administration_category_list"))
        self.assertContains(response, "Manage Categories")

    def test_administrator_can_create_category(self):
        self.login_as_admin()

        response = self.client.post(
            reverse("administration_category_create"),
            {"name": "Documents"},
        )

        self.assertRedirects(response, reverse("administration_category_list"))
        self.assertTrue(Category.objects.filter(name="Documents").exists())

    def test_category_name_is_trimmed_when_created(self):
        self.login_as_admin()

        self.client.post(
            reverse("administration_category_create"),
            {"name": "  Books  "},
        )

        self.assertTrue(Category.objects.filter(name="Books").exists())
        self.assertFalse(Category.objects.filter(name="  Books  ").exists())

    def test_empty_category_is_rejected(self):
        self.login_as_admin()

        response = self.client.post(
            reverse("administration_category_create"),
            {"name": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "name", "This field is required.")
        self.assertEqual(Category.objects.count(), 1)

    def test_duplicate_category_is_rejected(self):
        self.login_as_admin()

        response = self.client.post(
            reverse("administration_category_create"),
            {"name": "Electronics"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "name",
            "A category with this name already exists.",
        )
        self.assertEqual(Category.objects.filter(name="Electronics").count(), 1)

    def test_case_insensitive_duplicate_category_is_rejected(self):
        self.login_as_admin()

        response = self.client.post(
            reverse("administration_category_create"),
            {"name": "electronics"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "name",
            "A category with this name already exists.",
        )
        self.assertFalse(Category.objects.filter(name="electronics").exists())

    def test_administrator_can_edit_category(self):
        self.login_as_admin()

        response = self.client.post(
            reverse("administration_category_edit", args=[self.category.id]),
            {"name": "Devices"},
        )

        self.assertRedirects(response, reverse("administration_category_list"))
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Devices")

    def test_administrator_can_delete_unused_category(self):
        unused = Category.objects.create(name="Documents")
        self.login_as_admin()

        response = self.client.post(
            reverse("administration_category_delete", args=[unused.id])
        )

        self.assertRedirects(response, reverse("administration_category_list"))
        self.assertFalse(Category.objects.filter(id=unused.id).exists())

    def test_deletion_requires_post_confirmation(self):
        unused = Category.objects.create(name="Documents")
        self.login_as_admin()

        response = self.client.get(
            reverse("administration_category_delete", args=[unused.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete this category?")
        self.assertTrue(Category.objects.filter(id=unused.id).exists())

    def test_used_category_cannot_be_deleted(self):
        ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )
        self.login_as_admin()

        response = self.client.post(
            reverse("administration_category_delete", args=[self.category.id]),
            follow=True,
        )

        self.assertRedirects(response, reverse("administration_category_list"))
        self.assertContains(
            response,
            "This category cannot be deleted because it is currently used by one or more reports.",
        )
        self.assertTrue(Category.objects.filter(id=self.category.id).exists())

    def test_regular_user_cannot_create_edit_or_delete_through_direct_post(self):
        unused = Category.objects.create(name="Documents")
        self.login_as_regular_user()

        create_response = self.client.post(
            reverse("administration_category_create"),
            {"name": "Books"},
        )
        edit_response = self.client.post(
            reverse("administration_category_edit", args=[self.category.id]),
            {"name": "Devices"},
        )
        delete_response = self.client.post(
            reverse("administration_category_delete", args=[unused.id])
        )

        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(edit_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)
        self.assertFalse(Category.objects.filter(name="Books").exists())
        self.category.refresh_from_db()
        self.assertEqual(self.category.name, "Electronics")
        self.assertTrue(Category.objects.filter(id=unused.id).exists())

    def test_category_changes_appear_in_report_creation_and_edit_forms(self):
        self.login_as_admin()
        self.client.post(
            reverse("administration_category_create"),
            {"name": "Documents"},
        )

        self.client.login(username=self.creator.email, password="StrongPass123")
        create_response = self.client.get(reverse("reports:create_lost_report"))
        self.assertContains(create_response, "Documents")

        report = ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )
        edit_response = self.client.get(reverse("reports:edit_report", args=[report.id]))

        self.assertContains(edit_response, "Documents")
