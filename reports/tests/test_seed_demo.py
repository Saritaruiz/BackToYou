"""El comando seed_demo deja una base vacia lista para trabajar."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from accounts.models import User as UserModel
from ..models import Category, ItemReport


class SeedDemoCommandTests(TestCase):
    def run_command(self, *args):
        salida = StringIO()
        call_command("seed_demo", *args, stdout=salida)
        return salida.getvalue()

    def test_creates_the_category_catalog(self):
        self.assertEqual(Category.objects.count(), 0)

        self.run_command()

        self.assertGreaterEqual(Category.objects.count(), 8)
        self.assertTrue(Category.objects.filter(name="Documentos").exists())

    def test_without_demo_flag_no_users_or_reports_are_created(self):
        self.run_command()

        self.assertEqual(get_user_model().objects.count(), 0)
        self.assertEqual(ItemReport.objects.count(), 0)

    def test_demo_flag_creates_users_and_reports(self):
        self.run_command("--demo")

        User = get_user_model()
        self.assertTrue(User.objects.filter(email="demo.user@eafit.edu.co").exists())

        administrador = User.objects.get(email="demo.admin@eafit.edu.co")
        self.assertEqual(administrador.role, UserModel.Role.ADMINISTRATOR)
        self.assertEqual(ItemReport.objects.count(), 4)

    def test_demo_reports_cover_the_relevant_statuses(self):
        self.run_command("--demo")

        estados = set(ItemReport.objects.values_list("status", flat=True))
        self.assertIn(ItemReport.Status.ACTIVE, estados)
        self.assertIn(ItemReport.Status.PENDING_REVIEW, estados)
        self.assertIn(ItemReport.Status.RECOVERED, estados)

    def test_demo_users_can_log_in_with_the_documented_password(self):
        self.run_command("--demo")

        self.assertTrue(
            self.client.login(
                username="demo.user@eafit.edu.co",
                password="BackToYou.2026",
            )
        )

    def test_running_twice_does_not_duplicate_anything(self):
        self.run_command("--demo")
        categorias = Category.objects.count()
        reportes = ItemReport.objects.count()
        usuarios = get_user_model().objects.count()

        self.run_command("--demo")

        self.assertEqual(Category.objects.count(), categorias)
        self.assertEqual(ItemReport.objects.count(), reportes)
        self.assertEqual(get_user_model().objects.count(), usuarios)

    def test_a_recovered_demo_report_records_its_recovery_date(self):
        self.run_command("--demo")

        recuperado = ItemReport.objects.get(status=ItemReport.Status.RECOVERED)
        self.assertIsNotNone(recuperado.recovered_at)
        self.assertIsNotNone(recuperado.moderated_by)
