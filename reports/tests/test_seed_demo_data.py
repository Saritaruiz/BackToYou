from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from reports.models import Category, ItemReport


@override_settings(DEBUG=True)
class SeedDemoDataTests(TestCase):
    def seed(self):
        call_command('seed_demo_data', stdout=StringIO())

    def test_repeat_preserves_records_passwords_and_existing_category(self):
        category = Category.objects.create(name='electronics')
        self.seed()
        users = list(get_user_model().objects.values_list('pk', 'password'))
        reports = list(ItemReport.objects.values_list('pk', 'created_at', 'updated_at'))
        self.seed()
        self.assertEqual(get_user_model().objects.count(), 6)
        self.assertEqual(Category.objects.count(), 7)
        self.assertEqual(ItemReport.objects.count(), 30)
        self.assertEqual(users, list(get_user_model().objects.values_list('pk', 'password')))
        self.assertEqual(reports, list(ItemReport.objects.values_list('pk', 'created_at', 'updated_at')))
        self.assertEqual(ItemReport.objects.filter(category=category).count(), 5)
        admin = get_user_model().objects.get(role='ADMINISTRATOR')
        self.assertFalse(admin.is_staff)
        self.assertFalse(admin.is_superuser)

    def test_distribution_and_workflow_dates(self):
        self.seed()
        self.assertEqual(ItemReport.objects.filter(report_type='LOST').count(), 18)
        for status, count in [('ACTIVE', 14), ('RECOVERED', 6), ('PENDING_REVIEW', 6), ('REJECTED', 4)]:
            self.assertEqual(ItemReport.objects.filter(status=status).count(), count)
        for report in ItemReport.objects.all():
            self.assertLessEqual(report.event_date, report.created_at.date())
            if report.status == 'PENDING_REVIEW':
                self.assertIsNone(report.moderated_at)
                self.assertIsNone(report.moderated_by)
            else:
                self.assertGreaterEqual(report.moderated_at, report.created_at)
                self.assertIsNotNone(report.moderated_by)
            if report.status == 'RECOVERED':
                self.assertGreaterEqual(report.recovered_at, report.moderated_at)
            else:
                self.assertIsNone(report.recovered_at)

    @override_settings(DEBUG=False)
    def test_disabled_outside_development(self):
        with self.assertRaises(CommandError):
            self.seed()
        self.assertFalse(ItemReport.objects.exists())
        self.assertFalse(get_user_model().objects.exists())
