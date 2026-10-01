"""RF23 creation-only description preparation choices."""
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.test import TestCase, override_settings
from django.urls import reverse

from reports.forms import ItemReportCreationForm, ItemReportForm
from reports.models import Category, ItemReport
from reports.tests.test_rf22_ai_description import png_upload


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class DescriptionMethodSelectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='reporter', password='StrongPass123')
        self.category = Category.objects.create(name='Electronics')
        self.client.force_login(self.user)

    def url(self, kind='lost'):
        return reverse('reports:create_' + kind + '_report')

    def payload(self, **changes):
        data = dict(title='Calculator', description='My reviewed and edited description.',
                    category=self.category.pk, event_date='2026-08-10', location='Library',
                    description_method='manual')
        data.update(changes)
        return data

    def test_both_pages_display_choices_and_default_to_manual(self):
        for kind in ('lost', 'found'):
            with self.subTest(kind=kind):
                response = self.client.get(self.url(kind))
                self.assertContains(response, 'Description method')
                self.assertContains(response, 'AI-assisted')
                self.assertContains(response, 'Manual')
                self.assertEqual(response.context['form']['description_method'].value(), 'manual')
                self.assertContains(response, 'id="ai-controls" hidden')
                self.assertContains(response, 'name="description"')

    def test_manual_and_ai_submissions_preserve_normal_flow_for_both_types(self):
        for kind in ('lost', 'found'):
            for method in ('manual', 'ai'):
                with self.subTest(kind=kind, method=method):
                    response = self.client.post(self.url(kind), self.payload(description_method=method), follow=True)
                    self.assertContains(response, 'Report submitted successfully.')
                    report = ItemReport.objects.latest('pk')
                    self.assertEqual(report.description, 'My reviewed and edited description.')
                    self.assertEqual(report.report_type, kind.upper())
                    self.assertEqual(report.creator, self.user)
                    self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)
                    self.assertFalse(report.image)
        self.assertEqual(ItemReport.objects.count(), 4)

    def test_manual_submission_with_image(self):
        for kind in ('lost', 'found'):
            response = self.client.post(self.url(kind), self.payload(image=png_upload()))
            self.assertRedirects(response, reverse('reports:report_list'))
            self.assertTrue(ItemReport.objects.latest('pk').image.name.startswith('reports/'))

    def test_omitted_method_is_manual_and_does_not_mutate_input(self):
        data = self.payload()
        del data['description_method']
        form = ItemReportCreationForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['description_method'], 'manual')
        self.assertNotIn('description_method', data)
        self.assertRedirects(self.client.post(self.url(), data), reverse('reports:report_list'))

    def test_invalid_method_is_rejected(self):
        for kind in ('lost', 'found'):
            response = self.client.post(self.url(kind), self.payload(description_method='invalid'))
            self.assertEqual(response.status_code, 200)
            self.assertIn('description_method', response.context['form'].errors)
        self.assertFalse(ItemReport.objects.exists())

    def test_invalid_submission_preserves_method_and_text(self):
        for kind in ('lost', 'found'):
            for method in ('manual', 'ai'):
                response = self.client.post(self.url(kind), self.payload(title='', description_method=method))
                form = response.context['form']
                self.assertEqual(form['description_method'].value(), method)
                self.assertEqual(form['description'].value(), self.payload()['description'])
                self.assertIn('title', form.errors)
                if method == 'ai':
                    self.assertNotContains(response, 'id="ai-controls" hidden')
        self.assertFalse(ItemReport.objects.exists())

    @override_settings(HF_TOKEN='')
    def test_unavailable_ai_allows_selection_and_manual_fallback(self):
        response = self.client.get(self.url())
        self.assertContains(response, 'AI suggestions are not available right now')
        self.assertContains(response, 'AI-assisted')
        response = self.client.post(self.url(), self.payload())
        self.assertRedirects(response, reverse('reports:report_list'))

    def test_model_and_shared_form_have_no_method_field(self):
        with self.assertRaises(FieldDoesNotExist):
            ItemReport._meta.get_field('description_method')
        self.assertNotIn('description_method', ItemReportForm().fields)

    def test_owner_and_moderation_editing_have_no_selector(self):
        report = ItemReport.objects.create(
            title='Calculator', description='Original description', category=self.category,
            event_date='2026-08-10', location='Library', creator=self.user,
            report_type=ItemReport.ReportType.LOST,
        )
        response = self.client.get(reverse('reports:edit_report', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'description_method')
        admin = get_user_model().objects.create_user(username='admin', role='ADMINISTRATOR')
        self.client.force_login(admin)
        response = self.client.get(reverse('administration_report_edit', args=[report.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'description_method')
