"""Comando seed_categories: categorias base compartidas por el equipo."""

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ..management.commands.seed_categories import DEFAULT_CATEGORIES
from ..models import Category


class SeedCategoriesCommandTests(TestCase):
    def run_command(self):
        output = StringIO()
        call_command("seed_categories", stdout=output)
        return output.getvalue()

    def test_creates_all_default_categories_on_empty_database(self):
        self.run_command()

        self.assertCountEqual(
            Category.objects.values_list("name", flat=True),
            DEFAULT_CATEGORIES,
        )

    def test_running_twice_does_not_duplicate_categories(self):
        self.run_command()
        output = self.run_command()

        self.assertEqual(Category.objects.count(), len(DEFAULT_CATEGORIES))
        self.assertIn("Nothing to do", output)

    def test_keeps_existing_categories_untouched(self):
        custom = Category.objects.create(name="Umbrellas")
        existing = Category.objects.create(name="electronics")

        self.run_command()

        self.assertTrue(Category.objects.filter(pk=custom.pk, name="Umbrellas").exists())
        existing.refresh_from_db()
        self.assertEqual(existing.name, "electronics")
        self.assertEqual(Category.objects.filter(name__iexact="Electronics").count(), 1)
