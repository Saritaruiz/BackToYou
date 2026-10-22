"""NFR38 - Editorial Page Design, con lo pendiente de NFR31 y NFR32.

Lo visual se revisa con capturas. Estas pruebas cuidan las piezas de las que
depende: la seccion actual en el menu, la etiqueta propia de cada estado,
el foco visible y el movimiento reducido.
"""

import re
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Category, ItemReport


STYLESHEET = settings.BASE_DIR / "static" / "css" / "styles.css"


class EditorialPagesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.creator = User.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")

    def create_report(self, status=ItemReport.Status.ACTIVE, report_type=ItemReport.ReportType.LOST):
        return ItemReport.objects.create(
            title="Lost calculator",
            description="Grey scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=report_type,
            status=status,
        )

    def current_links(self, response):
        return re.findall(r'<a href="[^"]*" aria-current="page">([^<]+)</a>', response.content.decode())

    # NFR31: la seccion actual se marca en el menu, y solo una.
    def test_navigation_marks_only_the_current_section(self):
        self.client.login(username="creator@eafit.edu.co", password="StrongPass123")

        for url, section in (
            (reverse("home"), "Home"),
            (reverse("reports:report_list"), "Reports"),
            (reverse("reports:my_reports"), "My Reports"),
            (reverse("reports:create_lost_report"), "Create Lost"),
        ):
            with self.subTest(section=section):
                self.assertEqual(self.current_links(self.client.get(url)), [section])

    # NFR38: el lema "Lost. Found. Back to You." se ve en el inicio, como
    # antetitulo de la pregunta principal.
    def test_home_shows_the_slogan(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, '<span class="kicker">Lost. Found. Back to You.</span>', html=False)
        self.assertContains(response, "What did you <em>lose?</em>", html=False)

    # NFR32: el tipo y el estado del reporte llevan su propia clase.
    def test_report_card_and_detail_label_type_and_status(self):
        report = self.create_report(report_type=ItemReport.ReportType.FOUND)

        for url in (reverse("reports:report_list"), reverse("reports:report_detail", args=[report.id])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, '<span class="type-pill type-found">Found</span>', html=False)
                self.assertContains(response, '<span class="status-pill status-active">Active</span>', html=False)

    # NFR38: las tarjetas muestran el numero del reporte.
    def test_report_card_shows_the_report_number(self):
        report = self.create_report()

        response = self.client.get(reverse("reports:report_list"))

        self.assertContains(response, f"Nº {report.id:04d}")

    # NFR34: la cabecera saluda por el nombre y nunca muestra el correo.
    def test_header_greeting_never_shows_the_email(self):
        self.client.login(username="creator@eafit.edu.co", password="StrongPass123")

        response = self.client.get(reverse("home"))

        self.assertNotContains(response, "Hello, creator@eafit.edu.co")
        self.creator.first_name = "Sara"
        self.creator.save()
        self.assertContains(self.client.get(reverse("home")), "Hello, Sara")


class FrozenDatetime(datetime):
    """23 de octubre, 2:00 UTC: en Medellin todavia son las 9 p. m. del 22."""

    @classmethod
    def now(cls, tz=None):
        moment = datetime(2026, 10, 23, 2, 0, tzinfo=dt_timezone.utc)
        return moment.astimezone(tz) if tz else moment


class MastheadAndFooterTests(TestCase):
    # NFR38: la fecha de la cabecera es la de Medellin, aunque la app use UTC.
    def test_masthead_date_uses_the_colombian_day(self):
        with patch("django.template.defaulttags.datetime", FrozenDatetime):
            response = self.client.get(reverse("home"))

        self.assertContains(response, "Thursday, October 22, 2026")

    def test_footer_credits_the_team(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, "Sara Ruiz")
        self.assertContains(response, "Isabel Acevedo Acosta")


class EditorialStylesheetTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = STYLESHEET.read_text(encoding="utf-8")

    # NFR32: cada estado tiene su propio estilo.
    def test_every_status_has_its_own_style(self):
        for status in ItemReport.Status.values:
            with self.subTest(status=status):
                self.assertRegex(self.css, r"\.status-" + status.lower() + r" \{")
        for report_type in ItemReport.ReportType.values:
            with self.subTest(report_type=report_type):
                self.assertRegex(self.css, r"\.type-" + report_type.lower() + r" \{")

    # NFR32: foco visible en enlaces y botones, no solo en los campos.
    def test_links_and_buttons_show_keyboard_focus(self):
        self.assertRegex(self.css, r"a:focus-visible,\s*button:focus-visible,\s*\.button:focus-visible")

    # NFR32: si la persona pide reducir el movimiento, no hay animaciones.
    def test_reduced_motion_is_respected(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css)
