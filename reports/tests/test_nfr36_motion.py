"""NFR36 - Motion and Animations.

El movimiento se revisa en el navegador. Estas pruebas cuidan sus reglas:
las mismas duraciones en toda la app, ninguna animacion de mas de 500 ms,
"reducir movimiento" lo apaga todo, y las piezas que activan cada animacion.
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..models import Category, ItemReport


STYLESHEET = settings.BASE_DIR / "static" / "css" / "styles.css"


class MotionStylesheetTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = STYLESHEET.read_text(encoding="utf-8")

    # Las tres duraciones y tres curvas del manual de marca (seccion 10).
    def test_shared_durations_and_curves(self):
        for token in (
            "--dur-fast: 150ms;",
            "--dur-medium: 250ms;",
            "--dur-slow: 400ms;",
            "--ease-enter: cubic-bezier(0.2, 0, 0, 1);",
            "--ease-exit: cubic-bezier(0.4, 0, 1, 1);",
        ):
            with self.subTest(token=token):
                self.assertIn(token, self.css)

    # Given any animation, when it runs, then it lasts no more than 500 ms.
    def test_no_animation_lasts_more_than_500ms(self):
        durations = [float(value) for value in re.findall(r"(\d+(?:\.\d+)?)ms", self.css)]

        self.assertTrue(durations)
        self.assertLessEqual(max(durations), 500)

    # Given a button, when the user hovers over it, then it changes tone and
    # rises slightly.
    def test_buttons_rise_on_hover(self):
        hover = re.search(r"\.button:hover,\s*button:hover \{([^}]*)\}", self.css).group(1)

        self.assertIn("transform: translateY(-1px);", hover)

    # Given the mobile menu, when it opens, then it slides down.
    def test_mobile_menu_slides_down(self):
        self.assertRegex(self.css, r"\.nav-toggle:checked ~ \.site-nav \{[^}]*animation: menu-open")

    # Given a message, when it appears, then it slides in from the top.
    def test_messages_slide_in(self):
        self.assertRegex(self.css, r"\.message \{[^}]*animation: message-in")

    # Given a reduced-motion preference, when any animation would run, then
    # the change happens instantly, with no waits.
    def test_reduced_motion_turns_everything_off(self):
        block = self.css[self.css.index("@media (prefers-reduced-motion: reduce)"):]

        for rule in (
            "animation-duration: 0.01ms !important;",
            "animation-delay: 0ms !important;",
            "transition-duration: 0.01ms !important;",
            "navigation: none;",
        ):
            with self.subTest(rule=rule):
                self.assertIn(rule, block)


class MotionPagesTests(TestCase):
    def setUp(self):
        self.creator = get_user_model().objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.report = ItemReport.objects.create(
            title="House keys",
            description="Three keys on a green keyring",
            category=Category.objects.create(name="Keys"),
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )

    # La tarjeta tiene el marco que recorta la foto y el titulo que se subraya.
    def test_report_card_has_the_pieces_of_its_hover(self):
        response = self.client.get(reverse("reports:report_list"), {"view": "list"})
        home = self.client.get(reverse("home"))

        self.assertContains(home, '<article class="card report-card">', html=False)
        self.assertContains(home, '<div class="card-media">', html=False)
        self.assertContains(home, '<h3 class="card-title"><span>House keys</span></h3>', html=False)
        self.assertContains(response, 'class="view-toggle is-list"', html=False)
        self.assertContains(response, 'class="view-toggle-indicator"', html=False)

    # Los numeros del inicio cuentan hasta su valor real.
    def test_home_numbers_count_to_their_real_value(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'data-count-to="1"', html=False)

    # Marcar como recuperado activa la celebracion del aviso.
    def test_marking_recovered_shows_the_celebration_message(self):
        self.client.login(username="creator@eafit.edu.co", password="StrongPass123")

        response = self.client.post(
            reverse("reports:mark_report_recovered", args=[self.report.id]),
            follow=True,
        )

        self.assertContains(response, 'class="message message-success recovered"', html=False)
        self.assertContains(response, "It is back with its owner.")

    # Given an operation that takes more than one second, such as the AI
    # description, when it is running, then the system shows a loading
    # indicator.
    def test_ai_button_shows_a_loading_indicator(self):
        self.client.login(username="creator@eafit.edu.co", password="StrongPass123")

        response = self.client.get(reverse("reports:create_lost_report"))

        self.assertContains(response, 'button.setAttribute("aria-busy", "true");', html=False)
        self.assertContains(response, 'field.classList.add("ai-filled");', html=False)
