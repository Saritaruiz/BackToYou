"""Reportar es la idea del producto.

- Los botones para crear un reporte se destacan: en el menu son botones
  rellenos y en el inicio, dos bloques grandes debajo del buscador.
- El formulario de reporte dice que campos son obligatorios (*) y cuales son
  opcionales, para no adivinarlo al llenarlo.
"""

from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from ..models import Category, ItemReport


PASSWORD = "StrongPass123"
STYLESHEET = Path(settings.BASE_DIR) / "static" / "css" / "styles.css"


class ReportCallsToActionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("sara@eafit.edu.co", "sara@eafit.edu.co", PASSWORD)

    def test_home_offers_both_reports_as_big_blocks(self):
        response = self.client.get(reverse("home"))

        self.assertContains(
            response, f'<a class="cta-card cta-lost" href="{reverse("reports:create_lost_report")}">', html=False
        )
        self.assertContains(
            response, f'<a class="cta-card cta-found" href="{reverse("reports:create_found_report")}">', html=False
        )
        self.assertContains(response, "Report a lost item")
        self.assertContains(response, "Report a found item")

    # Sin sesion, el bloque lleva a iniciar sesion y despues al formulario.
    def test_blocks_work_before_logging_in(self):
        url = reverse("reports:create_found_report")

        response = self.client.get(url)

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}")

    def test_menu_shows_the_create_buttons_once_logged_in(self):
        self.assertNotContains(self.client.get(reverse("home")), 'class="nav-cta', html=False)

        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:report_list"))

        self.assertContains(
            response, f'<a class="nav-cta nav-cta-lost" href="{reverse("reports:create_lost_report")}">', html=False
        )
        self.assertContains(
            response, f'<a class="nav-cta nav-cta-found" href="{reverse("reports:create_found_report")}">', html=False
        )

    # Mismos colores que las etiquetas Lost y Found de los reportes.
    def test_buttons_are_filled_with_the_color_of_their_type(self):
        css = STYLESHEET.read_text(encoding="utf-8")

        for rule in (
            ".site-nav a.nav-cta-lost {\n    background: var(--charcoal);",
            ".site-nav a.nav-cta-found {\n    background: var(--accent);",
            ".cta-lost {\n    background: var(--charcoal);",
            ".cta-found {\n    background: var(--accent);",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, css)


class RequiredFieldsTests(TestCase):
    REQUIRED = ("title", "description", "category", "event_date", "location")

    def setUp(self):
        self.user = User.objects.create_user("sara@eafit.edu.co", "sara@eafit.edu.co", PASSWORD)
        self.category = Category.objects.create(name="Keys")
        self.client.force_login(self.user)

    def label(self, field, text, required):
        mark = (
            ' <span class="required-mark" aria-hidden="true">*</span>'
            if required
            else ' <span class="optional-mark">(optional)</span>'
        )
        return f'<label for="id_{field}">{text}{mark}</label>'

    def test_the_form_explains_the_marks_before_the_first_field(self):
        response = self.client.get(reverse("reports:create_lost_report"))
        html = response.content.decode()

        self.assertContains(response, "are required. The rest are optional.")
        self.assertLess(html.index('class="required-note"'), html.index('for="id_title"'))

    def test_lost_report_marks_every_field(self):
        response = self.client.get(reverse("reports:create_lost_report"))

        for field, text in zip(self.REQUIRED, ("Title", "Description", "Category", "Event date", "Location")):
            with self.subTest(field=field):
                self.assertContains(response, self.label(field, text, required=True), html=False)
        self.assertContains(response, self.label("image", "Image", required=False), html=False)

    # Quien encontro el objeto debe subir la foto (ver test_design_proposals).
    def test_found_report_marks_the_photo_as_required(self):
        response = self.client.get(reverse("reports:create_found_report"))

        self.assertContains(response, self.label("image", "Image", required=True), html=False)
        self.assertContains(response, 'name="image" accept="image/*" required', html=False)

    # El asterisco es visual; el lector de pantalla anuncia el atributo required.
    def test_required_fields_keep_the_required_attribute(self):
        response = self.client.get(reverse("reports:create_lost_report"))

        self.assertContains(response, 'name="title" maxlength="150" required', html=False)
        self.assertContains(response, 'name="location" maxlength="200" required', html=False)

    def test_help_text_is_linked_to_its_field(self):
        response = self.client.get(reverse("reports:create_lost_report"))

        self.assertContains(response, 'aria-describedby="id_image_helptext"', html=False)
        self.assertContains(response, 'id="id_image_helptext"', html=False)

    def test_edit_form_marks_the_fields_too(self):
        report = ItemReport.objects.create(
            title="House keys",
            description="Three keys",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.user,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )

        response = self.client.get(reverse("reports:edit_report", args=[report.id]))

        self.assertContains(response, self.label("title", "Title", required=True), html=False)
        self.assertContains(response, self.label("image", "Image", required=False), html=False)
