"""RF12 - Delete Report. Un test por criterio de aceptacion."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, ContactMessage, ItemReport


class DeleteReportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.creator = User.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.other_user = User.objects.create_user(
            username="other@eafit.edu.co",
            email="other@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")
        self.report = self.create_report()

    def create_report(self, title="Lost calculator", status=ItemReport.Status.ACTIVE):
        return ItemReport.objects.create(
            title=title,
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=status,
        )

    def delete_url(self, report=None):
        return reverse("reports:delete_report", args=[(report or self.report).id])

    def login_as_creator(self):
        self.client.login(username=self.creator.email, password="StrongPass123")

    # Given that the authenticated user is the report creator, when the user
    # confirms the deletion, then the report is no longer available.
    def test_creator_can_delete_their_own_report(self):
        self.login_as_creator()

        response = self.client.post(self.delete_url())

        self.assertRedirects(response, reverse("reports:report_list"))
        self.assertFalse(ItemReport.objects.filter(id=self.report.id).exists())

    # Given that the authenticated user is not the report creator, when the
    # user attempts to delete the report, then the system denies the action.
    def test_other_user_cannot_delete_the_report(self):
        self.client.login(
            username=self.other_user.email,
            password="StrongPass123",
        )

        get_response = self.client.get(self.delete_url())
        post_response = self.client.post(self.delete_url())

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        self.assertTrue(ItemReport.objects.filter(id=self.report.id).exists())

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.delete_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertTrue(ItemReport.objects.filter(id=self.report.id).exists())

    # Given a deletion request submitted without confirmation, when it is
    # received, then the system does not delete the report.
    def test_opening_the_confirmation_page_does_not_delete_the_report(self):
        self.login_as_creator()

        response = self.client.get(self.delete_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete this report?")
        self.assertContains(response, self.report.title)
        self.assertTrue(ItemReport.objects.filter(id=self.report.id).exists())

    # Given that the user cancels the confirmation, when the confirmation page
    # closes, then the report remains unchanged.
    def test_cancelling_leaves_the_report_unchanged(self):
        self.login_as_creator()
        before = ItemReport.objects.get(id=self.report.id)

        self.client.get(self.delete_url())
        self.client.get(reverse("reports:report_list"))

        after = ItemReport.objects.get(id=self.report.id)
        self.assertEqual(after.title, before.title)
        self.assertEqual(after.status, before.status)
        self.assertEqual(after.updated_at, before.updated_at)

    # Given a deleted report, when a user browses or searches reports, then the
    # report is not displayed.
    def test_deleted_report_disappears_from_the_list_and_from_search(self):
        kept = self.create_report(title="Lost umbrella")
        deleted_url = reverse("reports:report_detail", args=[self.report.id])
        kept_url = reverse("reports:report_detail", args=[kept.id])
        self.login_as_creator()

        self.client.post(self.delete_url())

        # Se busca el enlace al reporte y no su titulo: el titulo tambien
        # aparece en el mensaje de exito que se muestra tras el borrado.
        list_response = self.client.get(reverse("reports:report_list"))
        self.assertNotContains(list_response, deleted_url)
        self.assertContains(list_response, kept_url)

        search_response = self.client.get(
            reverse("reports:report_list"),
            {"q": "calculator"},
        )
        self.assertNotContains(search_response, deleted_url)
        self.assertTrue(ItemReport.objects.filter(id=kept.id).exists())

    # Given a deleted report, when a user opens its previous address directly,
    # then the system displays an informative not-available message.
    def test_previous_address_returns_not_found(self):
        detail_url = reverse("reports:report_detail", args=[self.report.id])
        self.login_as_creator()

        self.client.post(self.delete_url())

        self.assertEqual(self.client.get(detail_url).status_code, 404)

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_previous_address_shows_the_informative_page(self):
        detail_url = reverse("reports:report_detail", args=[self.report.id])
        self.login_as_creator()
        self.client.post(self.delete_url())

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 404)
        self.assertContains(
            response,
            "This report is not available",
            status_code=404,
        )

    # Given a deleted report that had contact messages associated with it, when
    # the deletion is completed, then those messages are removed together.
    def test_contact_messages_are_removed_with_the_report(self):
        kept_report = self.create_report(title="Lost umbrella")
        ContactMessage.objects.create(
            report=self.report,
            sender=self.other_user,
            message="I think I found your calculator",
        )
        kept_message = ContactMessage.objects.create(
            report=kept_report,
            sender=self.other_user,
            message="Is this your umbrella?",
        )
        self.login_as_creator()

        self.client.post(self.delete_url())

        self.assertFalse(
            ContactMessage.objects.filter(report_id=self.report.id).exists()
        )
        self.assertTrue(
            ContactMessage.objects.filter(id=kept_message.id).exists()
        )

    # Given a deleted report, when its creator opens their report history, then
    # the system handles it according to the retention policy: deleted reports
    # are not retained.
    def test_deleted_report_is_not_retained_for_the_creator(self):
        self.login_as_creator()

        self.client.post(self.delete_url())

        self.assertFalse(
            ItemReport.objects.filter(creator=self.creator, title="Lost calculator").exists()
        )

    def test_deleted_report_can_no_longer_be_edited_or_contacted(self):
        edit_url = reverse("reports:edit_report", args=[self.report.id])
        contact_url = reverse("reports:contact_reporter", args=[self.report.id])
        self.login_as_creator()

        self.client.post(self.delete_url())

        self.assertEqual(self.client.get(edit_url).status_code, 404)
        self.assertEqual(self.client.get(contact_url).status_code, 404)

    def test_reports_in_any_status_can_be_deleted_by_their_creator(self):
        self.login_as_creator()

        for status in (
            ItemReport.Status.PENDING_REVIEW,
            ItemReport.Status.REJECTED,
            ItemReport.Status.RECOVERED,
        ):
            report = self.create_report(title=f"Report {status}", status=status)

            response = self.client.post(self.delete_url(report))

            self.assertRedirects(response, reverse("reports:report_list"))
            self.assertFalse(ItemReport.objects.filter(id=report.id).exists())

    def test_delete_button_is_shown_only_to_the_creator(self):
        detail_url = reverse("reports:report_detail", args=[self.report.id])

        self.login_as_creator()
        self.assertContains(self.client.get(detail_url), self.delete_url())

        self.client.login(
            username=self.other_user.email,
            password="StrongPass123",
        )
        self.assertNotContains(self.client.get(detail_url), self.delete_url())

    def test_deleting_a_report_does_not_delete_its_category(self):
        self.login_as_creator()

        self.client.post(self.delete_url())

        self.assertTrue(Category.objects.filter(id=self.category.id).exists())
