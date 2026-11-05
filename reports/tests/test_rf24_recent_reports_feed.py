"""RF24: los reportes publicados se ven en el indice (Reports), no en el inicio.

El inicio ya no muestra el feed de reportes recientes: busca, ofrece las
categorias y lleva a crear un reporte. Estas pruebas cuidan que el indice
siga mostrando lo publicado, con la misma tarjeta, y nada privado.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from reports.models import Category, ItemReport


class HomeWithoutReportsTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='owner')
        self.category = Category.objects.create(name='Electronics')

    def test_home_does_not_list_reports(self):
        ItemReport.objects.create(
            title='Lost calculator', description='Scientific calculator', category=self.category,
            creator=self.owner, report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE, event_date='2026-08-10', location='Library')

        response = self.client.get(reverse('home'))

        self.assertNotIn('recent_reports', response.context)
        self.assertTemplateNotUsed(response, 'reports/_report_card.html')
        self.assertNotContains(response, 'Lost calculator')
        self.assertNotContains(response, 'Recently Published Reports')

    def test_home_still_leads_to_the_report_index(self):
        response = self.client.get(reverse('home'))

        self.assertContains(response, f'action="{reverse("reports:report_list")}"', html=False)


class ReportIndexTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='owner')
        self.admin = get_user_model().objects.create_user(username='admin', role='ADMINISTRATOR')
        self.category = Category.objects.create(name='Electronics')

    def report(self, title='Calculator', **changes):
        data = dict(title=title, description='Scientific calculator', category=self.category,
                    creator=self.owner, report_type=ItemReport.ReportType.LOST,
                    status=ItemReport.Status.ACTIVE, event_date='2026-08-10', location='Library')
        data.update(changes)
        return ItemReport.objects.create(**data)

    def index(self):
        return list(self.client.get(reverse('reports:report_list')).context['reports'])

    def test_index_public_and_authenticated_with_mixed_types(self):
        lost = self.report('Lost calculator')
        found = self.report('Found calculator', report_type='FOUND')
        for viewer in (None, self.owner):
            if viewer:
                self.client.force_login(viewer)
            response = self.client.get(reverse('reports:report_list'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(list(response.context['reports']), [found, lost])
            self.assertContains(response, 'Lost calculator')
            self.assertContains(response, 'Found calculator')

    def test_private_statuses_excluded_for_every_viewer(self):
        active = self.report('Visible')
        for status in ('PENDING_REVIEW', 'REJECTED', 'RECOVERED'):
            self.report('Private ' + status, status=status)
        for viewer in (None, self.owner, self.admin):
            if viewer:
                self.client.force_login(viewer)
            response = self.client.get(reverse('reports:report_list'))
            self.assertEqual(list(response.context['reports']), [active])
            for status in ('PENDING_REVIEW', 'REJECTED', 'RECOVERED'):
                self.assertNotContains(response, 'Private ' + status)

    def test_no_image_row_and_shared_partial(self):
        report = self.report()
        response = self.client.get(reverse('reports:report_list'))
        self.assertTemplateUsed(response, 'reports/_report_card.html')
        self.assertContains(response, report.title)
        self.assertContains(response, reverse('reports:report_detail', args=[report.pk]))
        self.assertNotContains(response, 'class="report-image"')
        self.assertNotContains(response, 'Edit Report')

    def test_image_card_preserves_image(self):
        self.report(image='reports/example.png')
        response = self.client.get(reverse('reports:report_list'))
        self.assertContains(response, 'reports/example.png')
        self.assertContains(response, 'class="report-image"')

    def test_empty_state(self):
        response = self.client.get(reverse('reports:report_list'))
        self.assertContains(response, 'No active reports are currently available.')

    @patch('reports.views.moderation.notify_report_approved')
    def test_approval_adds_report(self, notify):
        report = self.report(status='PENDING_REVIEW')
        self.assertEqual(self.index(), [])
        self.client.force_login(self.admin)
        response = self.client.post(reverse('administration_moderate_report', args=[report.pk]), {'action':'approve'})
        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertIsNotNone(report.moderated_at)
        self.assertEqual(self.index(), [report])

    def test_recovery_removes_report(self):
        report = self.report()
        self.assertEqual(self.index(), [report])
        self.client.force_login(self.owner)
        response = self.client.post(reverse('reports:mark_report_recovered', args=[report.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.index(), [])

    def test_browse_search_category_and_type_still_combine(self):
        now = timezone.now()
        other = Category.objects.create(name='Books')
        first = self.report('Match first')
        second = self.report('Match second')
        ItemReport.objects.filter(pk=first.pk).update(created_at=now-timedelta(days=2))
        self.report('Match found', report_type='FOUND')
        self.report('Match book', category=other)
        self.report('Match hidden', status='PENDING_REVIEW')
        self.report('Different', description='No search term')
        response = self.client.get(reverse('reports:report_list'), {'q':'Match', 'category':self.category.pk, 'type':'LOST'})
        self.assertEqual(list(response.context['reports']), [second, first])
