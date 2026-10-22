"""NFR37 - Category Iconography."""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from ..management.commands.seed_categories import DEFAULT_CATEGORIES
from ..models import Category, ItemReport
from ..templatetags.icons import icon_for_category


class CategoryIconTests(SimpleTestCase):
    # Cada categoria por defecto tiene su propio icono.
    def test_default_categories_have_their_own_icon(self):
        expected = {
            "Electronics": "laptop",
            "IDs & cards": "card",
            "Bottles": "bottle",
            "Clothing": "hoodie",
            "Bags & cases": "backpack",
            "Keys": "keys",
            "Books & notebooks": "book",
            "Accessories": "sunglasses",
            "Other": "tag",
        }
        self.assertEqual(set(expected), set(DEFAULT_CATEGORIES))
        for name, icon in expected.items():
            with self.subTest(name=name):
                self.assertEqual(icon_for_category(name), icon)

    # Una categoria creada por un Administrator sin icono propio usa el de "Other".
    def test_new_category_without_icon_uses_the_other_icon(self):
        self.assertEqual(icon_for_category("Musical instruments"), icon_for_category("Other"))


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
        self.assertContains(response, '<svg class="icon"', html=False)
