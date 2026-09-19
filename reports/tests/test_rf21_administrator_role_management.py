"""RF21 - Administrator Role Management.

Aprobar y rechazar reportes pendientes ya estaba cubierto por RF10
(ver test_sprint1.py). Estos tests cubren lo que agrega RF21: un
administrador tambien puede editar o eliminar un reporte mientras sigue
pendiente de revision, es decir, antes de que sea visible al publico.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Category, ItemReport


class AdministratorRoleManagementTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.regular = User.objects.create_user(
            username="regular@eafit.edu.co",
            email="regular@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.REGULAR_USER,
        )
        self.category = Category.objects.create(name="Electronics")

    def create_report(self, status=ItemReport.Status.PENDING_REVIEW, **kwargs):
        defaults = {
            "title": "Lost calculator",
            "description": "Black scientific calculator",
            "category": self.category,
            "event_date": "2026-08-10",
            "location": "Library",
            "creator": self.regular,
            "report_type": ItemReport.ReportType.LOST,
            "status": status,
        }
        defaults.update(kwargs)
        return ItemReport.objects.create(**defaults)

    def edit_url(self, report):
        return reverse("administration_report_edit", args=[report.id])

    def delete_url(self, report):
        return reverse("administration_report_delete", args=[report.id])

    def login_as(self, user):
        self.client.login(username=user.email, password="StrongPass123")

    # Given a pending report, when an Administrator edits its details,
    # then the system saves the changes and keeps it pending for review.
    def test_admin_can_edit_a_pending_report(self):
        report = self.create_report()
        self.login_as(self.admin)

        response = self.client.post(
            self.edit_url(report),
            {
                "title": "Lost graphing calculator",
                "description": report.description,
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Library",
            },
        )

        self.assertRedirects(
            response, reverse("administration_moderate_report", args=[report.id])
        )
        report.refresh_from_db()
        self.assertEqual(report.title, "Lost graphing calculator")
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)

    # Given a pending report, when an Administrator removes it, then the
    # system deletes it and it never becomes publicly visible.
    def test_admin_can_remove_a_pending_report(self):
        report = self.create_report()
        self.login_as(self.admin)

        response = self.client.post(self.delete_url(report))

        self.assertRedirects(response, reverse("administration_pending_reports"))
        self.assertFalse(ItemReport.objects.filter(id=report.id).exists())

    # Given that the Administrator cancels, when the confirmation page for
    # removal closes, then the report remains unchanged.
    def test_opening_the_remove_confirmation_page_does_not_delete_the_report(self):
        report = self.create_report()
        self.login_as(self.admin)

        response = self.client.get(self.delete_url(report))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, report.title)
        self.assertTrue(ItemReport.objects.filter(id=report.id).exists())

    # Given an already-moderated report (active), when an Administrator
    # attempts to edit or remove it through this path, then the system
    # denies the action: only reports still awaiting review qualify.
    def test_an_active_report_cannot_be_edited_through_this_endpoint(self):
        report = self.create_report(status=ItemReport.Status.ACTIVE)
        self.login_as(self.admin)

        response = self.client.get(self.edit_url(report))

        self.assertEqual(response.status_code, 404)

    def test_an_active_report_cannot_be_removed_through_this_endpoint(self):
        report = self.create_report(status=ItemReport.Status.ACTIVE)
        self.login_as(self.admin)

        response = self.client.post(self.delete_url(report))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(ItemReport.objects.filter(id=report.id).exists())

    # Given a Regular User, when the user attempts to edit or remove
    # someone else's pending report, then the system denies access.
    def test_a_regular_user_cannot_edit_a_pending_report(self):
        report = self.create_report()
        self.login_as(self.regular)

        response = self.client.get(self.edit_url(report))

        self.assertEqual(response.status_code, 403)

    def test_a_regular_user_cannot_remove_a_pending_report(self):
        report = self.create_report()
        self.login_as(self.regular)

        response = self.client.post(self.delete_url(report))

        self.assertEqual(response.status_code, 403)
        self.assertTrue(ItemReport.objects.filter(id=report.id).exists())

    def test_an_anonymous_visitor_is_redirected_to_login(self):
        report = self.create_report()

        response = self.client.get(self.edit_url(report))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
