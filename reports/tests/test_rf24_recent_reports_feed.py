"""RF24 homepage feed and public browsing regression coverage."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from reports.models import Category, ItemReport
from reports.querysets import recent_public_reports


class RecentReportsFeedTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='owner')
        self.admin = get_user_model().objects.create_user(username='admin', role='ADMINISTRATOR')
        self.category = Category.objects.create(name='Electronics')
        self.now = timezone.now()

    def report(self, title='Calculator', **changes):
        data = dict(title=title, description='Scientific calculator', category=self.category,
                    creator=self.owner, report_type=ItemReport.ReportType.LOST,
                    status=ItemReport.Status.ACTIVE, event_date='2026-08-10', location='Library')
        data.update(changes)
        return ItemReport.objects.create(**data)

    def feed(self):
        return list(self.client.get(reverse('home')).context['recent_reports'])

    def test_homepage_public_and_authenticated_with_mixed_types(self):
        lost = self.report('Lost calculator', moderated_at=self.now)
        found = self.report('Found calculator', report_type='FOUND', moderated_at=self.now+timedelta(minutes=1))
        for viewer in (None, self.owner):
            if viewer:
                self.client.force_login(viewer)
            response = self.client.get(reverse('home'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(response.context['recent_reports']), [found, lost])
            self.assertContains(response, 'Lost calculator')
            self.assertContains(response, 'Found calculator')
            self.assertContains(response, 'Recently Published Reports')
            self.assertContains(response, 'Browse All Reports')
            self.assertContains(response, 'href="' + reverse('reports:report_list') + '"')

    def test_private_statuses_excluded_for_every_viewer(self):
        active = self.report('Visible')
        for status in ('PENDING_REVIEW', 'REJECTED', 'RECOVERED'):
            self.report('Private ' + status, status=status)
        for viewer in (None, self.owner, self.admin):
            if viewer:
                self.client.force_login(viewer)
            response = self.client.get(reverse('home'))
            self.assertEqual(list(response.context['recent_reports']), [active])
            for status in ('PENDING_REVIEW', 'REJECTED', 'RECOVERED'):
                self.assertNotContains(response, 'Private ' + status)

    def test_publication_order_overrides_submission_order(self):
        first = self.report('Submitted earlier', moderated_at=self.now)
        second = self.report('Submitted later', moderated_at=self.now-timedelta(days=1))
        ItemReport.objects.filter(pk=first.pk).update(created_at=self.now-timedelta(days=3))
        self.assertEqual(self.feed(), [first, second])
        self.assertEqual(list(self.client.get(reverse('reports:report_list')).context['reports']), [second, first])

    def test_missing_moderation_time_falls_back_to_creation(self):
        old = self.report('Approved', moderated_at=self.now-timedelta(days=2))
        fallback = self.report('Legacy')
        ItemReport.objects.filter(pk=fallback.pk).update(created_at=self.now-timedelta(days=1))
        newest = self.report('Newly approved', moderated_at=self.now)
        self.assertEqual(self.feed(), [newest, fallback, old])

    def test_equal_publication_times_use_descending_id(self):
        first = self.report('First', moderated_at=self.now)
        second = self.report('Second', moderated_at=self.now)
        self.assertEqual(self.feed(), [second, first])

    def test_edit_does_not_bump_publication_order(self):
        old = self.report('Old', moderated_at=self.now-timedelta(days=2))
        new = self.report('New', moderated_at=self.now-timedelta(days=1))
        self.client.force_login(self.owner)
        response = self.client.post(reverse('reports:edit_report', args=[old.pk]), dict(
            title='Edited old', description='Edited description', category=self.category.pk,
            event_date='2026-08-10', location='Library'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.feed(), [new, old])

    def test_six_limit_is_after_filtering_and_ordering(self):
        active = [self.report(str(i), moderated_at=self.now+timedelta(minutes=i)) for i in range(8)]
        for status in ('PENDING_REVIEW', 'REJECTED', 'RECOVERED'):
            self.report(status, status=status, moderated_at=self.now+timedelta(days=1))
        self.assertEqual(self.feed(), list(reversed(active))[:6])

    def test_no_image_card_and_shared_partial(self):
        report = self.report()
        for url in (reverse('home'), reverse('reports:report_list')):
            response = self.client.get(url)
            self.assertTemplateUsed(response, 'reports/_report_card.html')
            self.assertContains(response, report.title)
            self.assertContains(response, reverse('reports:report_detail', args=[report.pk]))
            self.assertNotContains(response, '<img')
            self.assertNotContains(response, 'Edit Report')

    def test_image_card_preserves_image(self):
        self.report(image='reports/example.png')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'reports/example.png')
        self.assertContains(response, 'class="report-image"')

    def test_empty_state(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'No active reports are currently available.')
        self.assertContains(response, 'Browse All Reports')

    @patch('reports.views.moderation.notify_report_approved')
    def test_approval_adds_report(self, notify):
        report = self.report(status='PENDING_REVIEW')
        self.assertEqual(self.feed(), [])
        self.client.force_login(self.admin)
        response = self.client.post(reverse('administration_moderate_report', args=[report.pk]), {'action':'approve'})
        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertIsNotNone(report.moderated_at)
        self.assertEqual(self.feed(), [report])

    def test_recovery_removes_report(self):
        report = self.report()
        self.assertEqual(self.feed(), [report])
        self.client.force_login(self.owner)
        response = self.client.post(reverse('reports:mark_report_recovered', args=[report.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.feed(), [])

    def test_feed_categories_are_loaded_in_one_query(self):
        for i in range(6):
            self.report(str(i))
        with self.assertNumQueries(1):
            self.assertEqual([r.category.name for r in recent_public_reports()], ['Electronics']*6)

    def test_browse_search_category_and_type_still_combine(self):
        other = Category.objects.create(name='Books')
        first = self.report('Match first', moderated_at=self.now)
        second = self.report('Match second', moderated_at=self.now-timedelta(days=1))
        ItemReport.objects.filter(pk=first.pk).update(created_at=self.now-timedelta(days=2))
        self.report('Match found', report_type='FOUND')
        self.report('Match book', category=other)
        self.report('Match hidden', status='PENDING_REVIEW')
        self.report('Different', description='No search term')
        response = self.client.get(reverse('reports:report_list'), {'q':'Match', 'category':self.category.pk, 'type':'LOST'})
        self.assertEqual(list(response.context['reports']), [second, first])
