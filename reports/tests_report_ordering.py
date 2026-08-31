"""Orden de los listados cuando varios reportes comparten created_at.

`created_at` es auto_now_add, pero el reloj del sistema no siempre distingue
dos guardados consecutivos: en Windows su granularidad ronda los 15 ms. Cuando
las marcas de tiempo empatan, ordenar solo por `-created_at` deja el resultado
a merced del motor de base de datos. Estos tests fuerzan el empate para que la
regla de desempate quede verificada en cualquier sistema.
"""

from datetime import datetime, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from .models import Category, ItemReport

SAME_INSTANT = datetime(2026, 8, 25, 14, 30, 0, tzinfo=dt_timezone.utc)


class ReportOrderingTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.creator = UserModel.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.administrator = UserModel.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.category = Category.objects.create(name="Electronics")

    def create_reports(self, titles, status):
        reports = [
            ItemReport.objects.create(
                title=title,
                description="Item description",
                category=self.category,
                event_date="2026-08-10",
                location="Library",
                creator=self.creator,
                report_type=ItemReport.ReportType.LOST,
                status=status,
            )
            for title in titles
        ]

        # update() no pasa por save(), asi que evita auto_now_add y deja las
        # tres filas con exactamente la misma marca de tiempo.
        ItemReport.objects.filter(
            id__in=[report.id for report in reports]
        ).update(created_at=SAME_INSTANT)

        for report in reports:
            report.refresh_from_db()

        return reports

    def test_public_list_is_deterministic_when_created_at_ties(self):
        oldest, middle, newest = self.create_reports(
            ["First report", "Second report", "Third report"],
            ItemReport.Status.ACTIVE,
        )

        response = self.client.get(reverse("reports:report_list"))

        self.assertEqual(
            list(response.context["reports"]),
            [newest, middle, oldest],
        )

    def test_search_results_are_deterministic_when_created_at_ties(self):
        oldest, middle, newest = self.create_reports(
            ["Lost umbrella A", "Lost umbrella B", "Lost umbrella C"],
            ItemReport.Status.ACTIVE,
        )

        response = self.client.get(
            reverse("reports:report_list"),
            {"q": "umbrella"},
        )

        self.assertEqual(
            list(response.context["reports"]),
            [newest, middle, oldest],
        )

    def test_moderation_queue_is_deterministic_when_created_at_ties(self):
        oldest, middle, newest = self.create_reports(
            ["Pending one", "Pending two", "Pending three"],
            ItemReport.Status.PENDING_REVIEW,
        )
        self.client.login(
            username=self.administrator.email,
            password="StrongPass123",
        )

        response = self.client.get(reverse("administration_pending_reports"))

        self.assertEqual(
            list(response.context["reports"]),
            [newest, middle, oldest],
        )

    def test_report_history_is_deterministic_when_created_at_ties(self):
        oldest, middle, newest = self.create_reports(
            ["Mine one", "Mine two", "Mine three"],
            ItemReport.Status.ACTIVE,
        )
        self.client.login(
            username=self.creator.email,
            password="StrongPass123",
        )

        response = self.client.get(reverse("reports:my_reports"))

        self.assertEqual(
            list(response.context["reports"]),
            [newest, middle, oldest],
        )

    def test_distinct_timestamps_still_order_by_creation_time(self):
        first, second, third = self.create_reports(
            ["Alpha", "Beta", "Gamma"],
            ItemReport.Status.ACTIVE,
        )
        # El mas antiguo por id recibe la marca mas reciente: si el desempate
        # por id mandara sobre la fecha, este test fallaria.
        ItemReport.objects.filter(id=first.id).update(
            created_at=datetime(2026, 8, 26, 9, 0, 0, tzinfo=dt_timezone.utc)
        )
        for report in (first, second, third):
            report.refresh_from_db()

        response = self.client.get(reverse("reports:report_list"))

        self.assertEqual(
            list(response.context["reports"]),
            [first, third, second],
        )
