from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from reports.models import Category, ItemReport
from reports.statistics import lost_statistics
from reports.views.statistics import lost_statistics_dashboard


class LostStatisticsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin', role=User.Role.ADMINISTRATOR)
        self.user = User.objects.create_user(username='regular')
        self.category = Category.objects.create(name='Electronics')
        self.url = reverse('administration_lost_statistics')

    def report(self, **changes):
        values = dict(title='Calculator', description='Scientific calculator', creator=self.user,
                      category=self.category, report_type='LOST', status='ACTIVE',
                      event_date='2026-01-01', location='Library')
        values.update(changes)
        return ItemReport.objects.create(**values)

    def test_anonymous_redirect(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_regular_staff_and_superuser_flags_do_not_bypass(self):
        for staff, superuser in ((False, False), (True, False), (False, True), (True, True)):
            self.user.is_staff, self.user.is_superuser = staff, superuser
            self.user.save()
            self.client.force_login(self.user)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_inactive_admin_denied(self):
        self.admin.is_active = False
        request = RequestFactory().get(self.url)
        request.user = self.admin
        with self.assertRaises(PermissionDenied):
            lost_statistics_dashboard(request)

    def test_custom_admin_allowed_without_django_flags(self):
        self.client.force_login(self.admin)
        self.assertFalse(self.admin.is_staff)
        self.assertFalse(self.admin.is_superuser)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_status_counts_and_recovery_rate_exclude_found(self):
        for status in ItemReport.Status.values:
            self.report(status=status)
            self.report(status=status, report_type='FOUND')
        self.report(status='ACTIVE')
        result = lost_statistics()
        self.assertEqual(result['summary'], dict(total=5, active=2, recovered=1, pending=1, rejected=1, recovery_rate=33.3))
        self.assertEqual(result['categories'][0]['total'], 5)
        self.assertEqual(sum(row['total'] for row in result['months']), 5)

    def test_empty_and_found_only_render_with_zero_counts(self):
        self.client.force_login(self.admin)
        for found_only in (False, True):
            if found_only:
                self.report(report_type='FOUND')
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'N/A')
            self.assertContains(response, 'No Lost submissions')
            self.assertEqual(response.context['summary']['total'], 0)
            self.assertEqual(len(response.context['months']), 12)
            self.assertTrue(all(row['total'] == 0 for row in response.context['months']))

    def test_pending_and_rejected_have_no_recovery_denominator(self):
        self.report(status='PENDING_REVIEW')
        self.report(status='REJECTED')
        self.assertIsNone(lost_statistics()['summary']['recovery_rate'])

    def test_category_totals_and_deterministic_order(self):
        alpha = Category.objects.create(name='Accessories')
        Category.objects.create(name='Unused')
        self.report(category=alpha, status='RECOVERED')
        self.report()
        rows = lost_statistics()['categories']
        self.assertEqual([r['category__name'] for r in rows], ['Accessories', 'Electronics'])
        self.report(status='REJECTED')
        self.assertEqual([r['total'] for r in lost_statistics()['categories']], [2, 1])

    @patch('reports.statistics.timezone.localdate')
    def test_twelve_month_boundaries_and_zero_filling(self, localdate):
        localdate.return_value = datetime(2026, 1, 15).date()
        for year, month in ((2025, 1), (2025, 2), (2025, 12), (2026, 1), (2026, 2)):
            r = self.report()
            ItemReport.objects.filter(pk=r.pk).update(created_at=datetime(year, month, 1, tzinfo=dt_timezone.utc))
        rows = lost_statistics()['months']
        self.assertEqual(len(rows), 12)
        self.assertEqual((rows[0]['month'].year, rows[0]['month'].month), (2025, 2))
        self.assertEqual((rows[-1]['month'].year, rows[-1]['month'].month), (2026, 1))
        self.assertEqual([r['total'] for r in rows], [1]+[0]*9+[1, 1])

    @patch('reports.statistics.timezone.localdate')
    def test_timezone_month_boundary(self, localdate):
        localdate.return_value = datetime(2026, 1, 15).date()
        r = self.report()
        ItemReport.objects.filter(pk=r.pk).update(created_at=datetime(2026, 1, 1, 2, tzinfo=dt_timezone.utc))
        with timezone.override('America/Bogota'):
            rows = lost_statistics()['months']
        self.assertEqual(rows[-2]['total'], 1)
        self.assertEqual(rows[-1]['total'], 0)

    def test_edit_does_not_move_submission_month(self):
        r = self.report()
        before = lost_statistics()['months']
        r.description = 'Edited text'
        r.save()
        self.assertEqual(lost_statistics()['months'], before)

    @patch('reports.views.moderation.notify_report_approved')
    def test_approval_and_recovery_update_counts(self, notification):
        r = self.report(status='PENDING_REVIEW')
        self.client.force_login(self.admin)
        self.client.post(reverse('administration_moderate_report', args=[r.pk]), {'action': 'approve'})
        self.assertEqual(lost_statistics()['summary']['active'], 1)
        self.client.force_login(self.user)
        self.client.post(reverse('reports:mark_report_recovered', args=[r.pk]))
        summary = lost_statistics()['summary']
        self.assertEqual((summary['total'], summary['active'], summary['recovered'], summary['recovery_rate']), (1, 0, 1, 100.0))

    def test_read_only_and_existing_visibility(self):
        active = self.report()
        private = self.report(status='REJECTED')
        before = list(ItemReport.objects.values())
        self.client.force_login(self.admin)
        self.client.get(self.url)
        self.assertEqual(list(ItemReport.objects.values()), before)
        self.assertEqual(list(self.client.get(reverse('home')).context['recent_reports']), [active])
        self.assertEqual(self.client.get(reverse('reports:report_detail', args=[private.pk])).status_code, 404)

    def test_navigation_is_admin_only(self):
        for user in (self.user, self.admin):
            self.client.force_login(user)
            response = self.client.get(reverse('home'))
            if user == self.admin:
                self.assertContains(response, self.url)
                self.assertContains(self.client.get(reverse('administration')), self.url)
            else:
                self.assertNotContains(response, self.url)
