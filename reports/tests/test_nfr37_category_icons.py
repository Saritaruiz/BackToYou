"""NFR37 - Category Iconography."""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..management.commands.seed_categories import DEFAULT_CATEGORIES
from ..models import Category, ItemReport
from ..templatetags.icons import CATEGORY_ICONS, category_icon, icon_for_category


class CategoryIconTests(SimpleTestCase):
    # Cada categoria por defecto tiene su propio icono.
    def test_default_categories_have_their_own_icon(self):
        expected = {
            "Electronics": "electronics",
            "IDs & cards": "card",
            "Bottles": "bottle",
            "Clothing": "clothing",
            "Bags & cases": "bag",
            "Keys": "keys",
            "Books & notebooks": "book",
            "Accessories": "glasses",
            "Other": "tag",
        }
        self.assertEqual(set(expected), set(DEFAULT_CATEGORIES))
        for name, icon in expected.items():
            with self.subTest(name=name):
                self.assertEqual(icon_for_category(name), icon)

    # Una categoria creada por un Administrator sin icono propio usa el de "Other".
    def test_new_category_without_icon_uses_the_other_icon(self):
        self.assertEqual(icon_for_category("Musical instruments"), icon_for_category("Other"))


    # Los iconos de categoria son los del manual: cuadricula de 24 x 24 y un
    # solo color de detalle (icon-fill).
    def test_category_icons_follow_the_brand_manual_grid(self):
        for name in CATEGORY_ICONS:
            with self.subTest(name=name):
                self.assertIn("icon-fill", CATEGORY_ICONS[name])
        self.assertIn('viewBox="0 0 24 24"', category_icon("Keys"))
        self.assertIn('class="icon category-icon"', category_icon("Keys"))


class ReportWithoutPhotoTests(TestCase):
    # Un reporte sin foto muestra el icono de su categoria, no una caja vacia.
    def test_card_without_photo_shows_the_category_icon(self):
        creator = get_user_model().objects.create_user(
            username="creator@eafit.edu.co", email="creator@eafit.edu.co", password="StrongPass123",
        )
        ItemReport.objects.create(
            title="House keys",
            description="Three keys",
            category=Category.objects.create(name="Keys"),
            event_date="2026-08-10",
            location="Library",
            creator=creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )

        response = self.client.get(reverse("home"))

        self.assertContains(response, '<div class="report-placeholder">', html=False)
        self.assertContains(response, '<svg class="icon category-icon"', html=False)


class CategoryPickerTests(TestCase):
    def setUp(self):
        self.keys = Category.objects.create(name="Keys")
        self.bottles = Category.objects.create(name="Bottles")

    # En el indice la categoria se elige con casillas que muestran su icono.
    def test_index_shows_one_tile_with_icon_per_category(self):
        response = self.client.get(reverse("reports:report_list"))

        self.assertContains(response, 'class="category-tile"', count=3, html=False)
        self.assertContains(response, 'type="radio"', count=3, html=False)
        self.assertNotContains(response, 'id="category-filter"', html=False)
        self.assertContains(response, category_icon("Keys"), html=False)
        self.assertContains(response, category_icon("Bottles"), html=False)

    # Sin filtro queda marcada "All"; con filtro, la categoria elegida.
    def test_selected_category_is_checked(self):
        response = self.client.get(reverse("reports:report_list"))
        self.assertContains(response, '<input type="radio" name="category" value="" checked>', html=False)

        response = self.client.get(reverse("reports:report_list"), {"category": self.keys.id})
        content = response.content.decode()
        self.assertNotIn('<input type="radio" name="category" value="" checked>', content)
        keys_input = content.split(f'value="{self.keys.id}"', 1)[1].split(">", 1)[0]
        self.assertIn("checked", keys_input)
