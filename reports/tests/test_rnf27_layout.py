"""RNF27 - Layout and Page Centering.

Lo visual (centrado, columnas, sin desplazamiento horizontal) se revisa con
capturas en 1440, 768 y 360 px. Estas pruebas cuidan la estructura de la
que depende ese resultado, para que no se pierda en cambios futuros.
"""

import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Category


STYLESHEET = settings.BASE_DIR / "static" / "css" / "styles.css"


class LayoutStructureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        User.objects.create_user(
            username="user@eafit.edu.co",
            email="user@eafit.edu.co",
            password="StrongPass123",
        )
        Category.objects.create(name="Electronics")

    def test_header_content_and_footer_share_the_same_container(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'class="header-inner"')
        self.assertContains(response, 'class="page-shell"')
        self.assertContains(response, 'class="footer-inner"')

    def test_small_screens_get_a_menu_button_linked_to_the_navigation(self):
        response = self.client.get(reverse("home"))

        self.assertContains(response, 'class="nav-toggle" type="checkbox" id="nav-toggle"')
        self.assertContains(response, '<label class="nav-toggle-label" for="nav-toggle">Menu</label>')

    def test_admin_tables_scroll_inside_their_panel(self):
        self.client.login(username="admin@eafit.edu.co", password="StrongPass123")

        for url_name in (
            "administration_user_list",
            "administration_administrator_list",
            "administration_category_list",
        ):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))
                self.assertRegex(
                    response.content.decode(),
                    r'class="panel table-wrap"[^>]*>\s*<table class="data-table"',
                )


class LayoutStylesheetTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = STYLESHEET.read_text(encoding="utf-8")

    def test_container_is_1120px_with_32px_and_16px_gutters(self):
        self.assertIn("--container-max: 1120px;", self.css)
        self.assertIn("--gutter: 32px;", self.css)
        self.assertRegex(self.css, r"@media \(max-width: 600px\) \{\s*:root \{\s*--gutter: 16px;")
        self.assertIn(
            "width: min(var(--container-max), calc(100% - 2 * var(--gutter)));",
            self.css,
        )

    def test_report_grid_uses_4_2_and_1_columns(self):
        self.assertRegex(self.css, r"\.grid \{[^}]*repeat\(4, minmax\(0, 1fr\)\)")
        self.assertRegex(
            self.css,
            r"@media \(max-width: 1080px\) \{\s*\.grid \{\s*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\);",
        )
        self.assertRegex(
            self.css,
            r"@media \(max-width: 599px\) \{\s*\.grid \{\s*grid-template-columns: 1fr;",
        )

    def test_forms_and_details_are_centered(self):
        form_rule = re.search(r"\.form-card \{([^}]*)\}", self.css).group(1)
        self.assertIn("margin-inline: auto;", form_rule)
        self.assertIn("max-width: var(--form-max);", form_rule)
        self.assertIn("--form-max: 680px;", self.css)
        self.assertIn("--detail-max: 880px;", self.css)

    def test_footer_stays_at_the_bottom_of_short_pages(self):
        self.assertRegex(self.css, r"body \{\s*min-height: 100vh;[^}]*flex-direction: column;")
        self.assertRegex(self.css, r"\.page-shell \{\s*flex: 1 0 auto;")

    def test_card_actions_align_at_the_bottom_of_each_card(self):
        self.assertRegex(self.css, r"\.card-body > :last-child \{\s*margin-top: auto;")

    def test_messages_match_the_width_of_centered_forms(self):
        self.assertRegex(
            self.css,
            r"\.page-shell:has\(> \.form-card\) > \.messages \{[^}]*max-width: var\(--form-max\);",
        )

    def test_open_mobile_menu_does_not_stay_fixed_over_the_content(self):
        self.assertRegex(
            self.css,
            r"\.site-header:has\(\.nav-toggle:checked\) \{\s*position: static;",
        )

    def test_spacing_scale_uses_multiples_of_4px(self):
        values = [int(value) for value in re.findall(r"--space-\d+: (\d+)px;", self.css)]

        self.assertTrue(values)
        self.assertTrue(all(value % 4 == 0 for value in values))
