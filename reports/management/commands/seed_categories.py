"""Crea las categorias base de BackToYou en la base de datos local.

Uso (una sola vez, despues de migrate):
    python manage.py seed_categories

Solo agrega las que falten. No modifica ni borra las que ya existen, asi que
se puede correr varias veces sin problema. Los administradores pueden
editarlas despues desde Administration > Categories (RF14).
"""

from django.core.management.base import BaseCommand

from reports.models import Category


DEFAULT_CATEGORIES = [
    "Electronics",
    "IDs & cards",
    "Bottles",
    "Clothing",
    "Bags & cases",
    "Keys",
    "Books & notebooks",
    "Accessories",
    "Other",
]


class Command(BaseCommand):
    help = "Create the default BackToYou item categories that do not exist yet."

    def handle(self, *args, **options):
        existing = {name.lower() for name in Category.objects.values_list("name", flat=True)}
        created = [name for name in DEFAULT_CATEGORIES if name.lower() not in existing]

        Category.objects.bulk_create(Category(name=name) for name in created)

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created {len(created)} categories: {', '.join(created)}"))
        else:
            self.stdout.write("All default categories already exist. Nothing to do.")
