"""Deja la base de datos lista para trabajar sin depender de un db.sqlite3 compartido.

    python manage.py seed_demo            # solo el catalogo de categorias
    python manage.py seed_demo --demo     # ademas, usuarios y reportes de ejemplo

El comando es idempotente: correrlo dos veces no duplica nada.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User as UserModel
from reports.models import Category, ItemReport

CATEGORIAS = [
    "Electrónica",
    "Documentos",
    "Llaves",
    "Ropa y accesorios",
    "Libros y cuadernos",
    "Bolsos y maletas",
    "Deportes",
    "Otros",
]

DEMO_PASSWORD = "BackToYou.2026"

DEMO_USUARIOS = [
    ("demo.user@eafit.edu.co", "Demo User", UserModel.Role.REGULAR_USER),
    ("demo.admin@eafit.edu.co", "Demo Admin", UserModel.Role.ADMINISTRATOR),
]

DEMO_REPORTES = [
    ("Portátil en el bloque 19", "Portátil gris en un maletín negro.",
     "Electrónica", ItemReport.ReportType.LOST, ItemReport.Status.ACTIVE, "Bloque 19"),
    ("Carné estudiantil encontrado", "Carné a nombre de un estudiante de pregrado.",
     "Documentos", ItemReport.ReportType.FOUND, ItemReport.Status.ACTIVE, "Cafetería central"),
    ("Juego de llaves", "Llavero azul con tres llaves.",
     "Llaves", ItemReport.ReportType.FOUND, ItemReport.Status.PENDING_REVIEW, "Biblioteca"),
    ("Chaqueta negra", "Chaqueta impermeable talla M.",
     "Ropa y accesorios", ItemReport.ReportType.LOST, ItemReport.Status.RECOVERED, "Bloque 38"),
]


class Command(BaseCommand):
    help = "Crea el catálogo de categorías y, con --demo, datos de ejemplo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo",
            action="store_true",
            help="Crea además usuarios y reportes de ejemplo.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        creadas = 0
        for nombre in CATEGORIAS:
            _, nueva = Category.objects.get_or_create(name=nombre)
            creadas += int(nueva)

        self.stdout.write(
            f"Categorías: {creadas} creadas, "
            f"{Category.objects.count()} en total."
        )

        if not options["demo"]:
            self.stdout.write(
                self.style.SUCCESS("Listo. Usa --demo para datos de ejemplo.")
            )
            return

        self._crear_demo()

    def _crear_demo(self):
        User = get_user_model()

        usuarios = {}
        for correo, nombre, rol in DEMO_USUARIOS:
            usuario = User.objects.filter(email__iexact=correo).first()
            if usuario is None:
                usuario = User.objects.create_user(
                    username=correo,
                    email=correo,
                    password=DEMO_PASSWORD,
                    first_name=nombre,
                    role=rol,
                )
                self.stdout.write(f"  usuario creado: {correo} ({rol})")
            usuarios[rol] = usuario

        creador = usuarios[UserModel.Role.REGULAR_USER]
        administrador = usuarios[UserModel.Role.ADMINISTRATOR]

        nuevos = 0
        for titulo, descripcion, categoria, tipo, estado, lugar in DEMO_REPORTES:
            if ItemReport.objects.filter(title=titulo).exists():
                continue

            reporte = ItemReport(
                title=titulo,
                description=descripcion,
                category=Category.objects.get(name=categoria),
                report_type=tipo,
                status=estado,
                event_date=timezone.now().date(),
                location=lugar,
                creator=creador,
            )

            # Un reporte publicado o rechazado pasó por moderación.
            if estado in (ItemReport.Status.ACTIVE, ItemReport.Status.REJECTED):
                reporte.moderated_by = administrador
                reporte.moderated_at = timezone.now()

            if estado == ItemReport.Status.RECOVERED:
                reporte.moderated_by = administrador
                reporte.moderated_at = timezone.now()
                reporte.recovered_at = timezone.now()

            reporte.save()
            nuevos += 1

        self.stdout.write(f"Reportes de ejemplo: {nuevos} creados.")
        self.stdout.write(
            self.style.SUCCESS(
                f"Listo. Entra con demo.user@eafit.edu.co o "
                f"demo.admin@eafit.edu.co / {DEMO_PASSWORD}"
            )
        )
