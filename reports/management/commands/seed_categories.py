"""Crea las categorias base de BackToYou en la base de datos local.

Uso (una sola vez, despues de migrate):
    python manage.py seed_categories

Solo agrega las que falten. No modifica ni borra las que ya existen, asi que
se puede correr varias veces sin problema. Los administradores pueden
editarlas despues desde Administration > Categories (RF14).
"""

from django.core.management.base import BaseCommand
from django.utils.translation import gettext_noop

from reports.models import Category


# Se guardan en ingles. gettext_noop las deja en el archivo de traducciones,
# asi las plantillas las muestran en el idioma de la pagina con
# {% translate category.name %}. Una categoria que cree un administrador se
# ve tal como la escribio.
DEFAULT_CATEGORIES = [
    gettext_noop("Electronics"),
    gettext_noop("IDs & cards"),
    gettext_noop("Bottles"),
    gettext_noop("Clothing"),
    gettext_noop("Bags & cases"),
    gettext_noop("Keys"),
    gettext_noop("Books & notebooks"),
    gettext_noop("Accessories"),
    gettext_noop("Other"),
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
