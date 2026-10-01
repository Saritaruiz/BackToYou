"""Las paginas de error explican que paso en vez de mostrar una pantalla tecnica.

RF18 View Report Details: un reporte no publicado devuelve 404 y un mensaje
neutral que no revela si existe. Las acciones de dueno/admin sobre un recurso
que el usuario ya sabe que existe devuelven 403 con un mensaje explicito.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Category, ItemReport


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
class ErrorPagesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.creator = User.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.other_user = User.objects.create_user(
            username="other@eafit.edu.co",
            email="other@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")

    def create_report(self, status=ItemReport.Status.ACTIVE, creator=None):
        return ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=creator or self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=status,
        )

    def login_as(self, user):
        self.client.login(username=user.email, password="StrongPass123")

    # --- RF18: el 404 se mantiene neutral, sin revelar existencia --------

    def test_a_missing_report_shows_the_neutral_not_available_page(self):
        response = self.client.get(
            reverse("reports:report_detail", args=[9999])
        )

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page is not available", status_code=404)
        self.assertNotContains(response, "permission", status_code=404)

    def test_an_unpublished_report_shows_the_same_neutral_page_to_non_owners(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as(self.other_user)

        response = self.client.get(
            reverse("reports:report_detail", args=[report.id])
        )

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page is not available", status_code=404)
        self.assertNotContains(response, "permission", status_code=404)

    def test_anonymous_visitor_gets_the_same_neutral_page(self):
        report = self.create_report(status=ItemReport.Status.REJECTED)

        response = self.client.get(
            reverse("reports:report_detail", args=[report.id])
        )

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page is not available", status_code=404)

    # --- Acciones de dueno: 403 explicito, el recurso ya se sabe que existe

    def test_editing_someone_elses_report_explains_the_permission_issue(self):
        report = self.create_report()
        self.login_as(self.other_user)

        response = self.client.get(reverse("reports:edit_report", args=[report.id]))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "don't have permission", status_code=403)

    def test_editing_a_rejected_report_explains_the_permission_issue(self):
        report = self.create_report(status=ItemReport.Status.REJECTED)
        self.login_as(self.creator)

        response = self.client.get(reverse("reports:edit_report", args=[report.id]))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "don't have permission", status_code=403)

    def test_recovering_a_pending_report_explains_the_permission_issue(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as(self.creator)

        response = self.client.get(
            reverse("reports:mark_report_recovered", args=[report.id])
        )

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "don't have permission", status_code=403)

    def test_the_403_page_offers_a_way_out(self):
        report = self.create_report(status=ItemReport.Status.REJECTED)
        self.login_as(self.creator)

        response = self.client.get(reverse("reports:edit_report", args=[report.id]))

        self.assertContains(response, reverse("reports:my_reports"), status_code=403)
        self.assertContains(response, reverse("reports:report_list"), status_code=403)

    # --- Panel de administracion: mismo 403, sin admin no hay acceso ------

    def test_regular_user_hitting_the_admin_panel_gets_the_permission_page(self):
        self.login_as(self.other_user)

        response = self.client.get(reverse("administration"))

        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "don't have permission", status_code=403)
