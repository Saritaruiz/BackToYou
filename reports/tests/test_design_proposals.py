"""Mejoras de diseno sobre el estilo editorial (NFR38).

1. Buscar primero en el inicio.
2. Sin cajas grises: con foto en tarjetas, sin foto en filas; foto obligatoria en Found.
3. Cabecera compacta en las paginas internas y franja con datos reales.
4. Una accion principal por pantalla; borrar va en una zona de riesgo.
5. Confianza: numeros reales y guia de entrega segura.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from ..models import Category, ItemReport
from ..statistics import community_numbers


class DesignProposalsTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.creator = UserModel.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.visitor = UserModel.objects.create_user(
            username="visitor@eafit.edu.co",
            email="visitor@eafit.edu.co",
            password="StrongPass123",
        )
        self.admin = UserModel.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.category = Category.objects.create(name="Keys")

    def report(self, title="House keys", status=ItemReport.Status.ACTIVE,
               report_type=ItemReport.ReportType.LOST, **extra):
        return ItemReport.objects.create(
            title=title,
            description="Three keys on a green keyring",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=report_type,
            status=status,
            **extra,
        )

    # 1. El inicio pregunta que perdio la persona y busca en el indice.
    def test_home_search_goes_to_the_report_index(self):
        self.report()

        response = self.client.get(reverse("home"))

        self.assertContains(response, f'action="{reverse("reports:report_list")}"', html=False)
        self.assertContains(response, 'name="q"', html=False)
        self.assertContains(response, "Search 1 report")

    def test_home_offers_one_shortcut_per_category(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, f'{reverse("reports:report_list")}?category={self.category.id}', html=False)

    # 2. En el indice, con foto en tarjetas y sin foto en filas.
    def test_report_index_shows_photos_as_cards_and_the_rest_as_rows(self):
        with_photo = self.report("Keys with photo", image="reports/keys.png")
        without_photo = self.report("Keys without photo")

        response = self.client.get(reverse("reports:report_list"))

        self.assertEqual(response.context["reports_with_photo"], [with_photo])
        self.assertEqual(response.context["reports_without_photo"], [without_photo])
        self.assertContains(response, 'class="report-row"', count=1, html=False)

    def test_all_as_list_shows_every_report_as_a_row(self):
        self.report("Keys with photo", image="reports/keys.png")
        self.report("Keys without photo")

        response = self.client.get(reverse("reports:report_list"), {"view": "list"})

        self.assertContains(response, 'class="report-row"', count=2, html=False)

    def test_found_report_requires_a_photo(self):
        self.client.login(username="creator@eafit.edu.co", password="StrongPass123")

        response = self.client.post(
            reverse("reports:create_found_report"),
            {
                "title": "Found keys",
                "description": "Keys on a green keyring",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Library",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "image",
            "Add a photo of the item you found so its owner can recognize it.",
        )
        self.assertFalse(ItemReport.objects.exists())

    def test_lost_report_photo_stays_optional(self):
        self.client.login(username="creator@eafit.edu.co", password="StrongPass123")

        self.client.post(
            reverse("reports:create_lost_report"),
            {
                "title": "Lost keys",
                "description": "Keys on a green keyring",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Library",
            },
        )

        self.assertTrue(ItemReport.objects.filter(title="Lost keys").exists())

    # 3. La cabecera de periodico solo va en el inicio.
    def test_inner_pages_use_the_compact_header(self):
        home = self.client.get(reverse("home"))
        index = self.client.get(reverse("reports:report_list"))

        self.assertContains(home, '<header class="site-header">', html=False)
        self.assertContains(index, '<header class="site-header is-compact">', html=False)

    # 4. Una accion principal; borrar va aparte, en la zona de riesgo.
    def test_creator_deletes_from_the_danger_zone(self):
        report = self.report()
        self.client.login(username="creator@eafit.edu.co", password="StrongPass123")

        response = self.client.get(reverse("reports:report_detail", args=[report.id]))

        delete_url = reverse("reports:delete_report", args=[report.id])
        self.assertContains(response, 'class="danger-zone"', html=False)
        self.assertContains(response, f'<a class="danger-link" href="{delete_url}">Delete Report</a>', html=False)
        self.assertNotContains(response, 'class="button danger"', html=False)

    def test_moderator_removes_from_the_danger_zone(self):
        report = self.report(status=ItemReport.Status.PENDING_REVIEW)
        self.client.login(username="admin@eafit.edu.co", password="StrongPass123")

        response = self.client.get(reverse("administration_moderate_report", args=[report.id]))

        remove_url = reverse("administration_report_delete", args=[report.id])
        self.assertContains(response, f'<a class="danger-link" href="{remove_url}">Remove</a>', html=False)

    # 5. Guia de entrega segura en cada reporte publicado.
    def test_active_report_shows_the_safe_handover_guide(self):
        report = self.report()
        self.client.login(username="visitor@eafit.edu.co", password="StrongPass123")

        response = self.client.get(reverse("reports:report_detail", args=[report.id]))

        self.assertContains(response, "Return it <em>safely</em>", html=False)

    def test_community_numbers_count_real_reports(self):
        now = timezone.now()
        self.report("Active lost")
        self.report("Recovered lost", status=ItemReport.Status.RECOVERED, recovered_at=now - timedelta(days=2))
        self.report("Old recovery", status=ItemReport.Status.RECOVERED, recovered_at=now - timedelta(days=20))
        self.report("Pending", status=ItemReport.Status.PENDING_REVIEW)

        numbers = community_numbers()

        self.assertEqual(numbers["active"], 1)
        self.assertEqual(numbers["recovered"], 2)
        self.assertEqual(numbers["returned_this_week"], 1)
        self.assertEqual(numbers["new_last_day"], 1)
        # RF25: Recovered / (Active + Recovered) entre los Lost.
        self.assertEqual(numbers["recovery_rate"], 66.7)

    def test_community_numbers_without_reports_have_no_rate(self):
        self.assertIsNone(community_numbers()["recovery_rate"])
