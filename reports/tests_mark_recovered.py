"""RF13 - Mark Item as Recovered. Un test por criterio de aceptacion."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, ItemReport


class MarkItemAsRecoveredTests(TestCase):
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

    def recover_url(self, report=None):
        return reverse(
            "reports:mark_report_recovered",
            args=[(report or self.report).id],
        )

    def login_as_creator(self):
        self.client.login(username=self.creator.email, password="StrongPass123")

    # Given an Active report owned by the authenticated user, when the user
    # confirms the action, then the system changes the status to Recovered.
    def test_creator_can_mark_their_active_report_as_recovered(self):
        self.login_as_creator()

        response = self.client.post(self.recover_url())

        self.assertRedirects(response, reverse("reports:report_list"))

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.RECOVERED)

    # Given a report that is not owned by the authenticated user, when the user
    # attempts to mark it as recovered, then the system denies the action.
    def test_other_user_cannot_mark_the_report_as_recovered(self):
        self.client.login(
            username=self.other_user.email,
            password="StrongPass123",
        )

        get_response = self.client.get(self.recover_url())
        post_response = self.client.post(self.recover_url())

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.ACTIVE)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.recover_url())

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.ACTIVE)

    # Given a report with Pending Review or Rejected status, when the user
    # attempts to mark it as recovered, then the system prevents the action.
    def test_pending_or_rejected_reports_cannot_be_marked_as_recovered(self):
        self.login_as_creator()

        for status in (
            ItemReport.Status.PENDING_REVIEW,
            ItemReport.Status.REJECTED,
        ):
            report = self.create_report(title=f"Report {status}", status=status)

            get_response = self.client.get(self.recover_url(report))
            post_response = self.client.post(self.recover_url(report))

            self.assertEqual(get_response.status_code, 403)
            self.assertEqual(post_response.status_code, 403)

            report.refresh_from_db()
            self.assertEqual(report.status, status)

    # Given a report that is already Recovered, when the user attempts to mark
    # it as recovered again, then the system prevents the action and the status
    # remains unchanged.
    def test_already_recovered_report_cannot_be_recovered_again(self):
        report = self.create_report(
            title="Already recovered",
            status=ItemReport.Status.RECOVERED,
        )
        report.recovered_at = timezone.now()
        report.save(update_fields=["recovered_at"])
        first_recovered_at = report.recovered_at
        self.login_as_creator()

        response = self.client.post(self.recover_url(report))

        self.assertEqual(response.status_code, 403)

        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.RECOVERED)
        self.assertEqual(report.recovered_at, first_recovered_at)

    # Given a Recovered report, when users browse or search reports, then the
    # report is excluded from the public report list.
    def test_recovered_report_leaves_the_public_list_and_search(self):
        kept = self.create_report(title="Lost umbrella")
        recovered_url = reverse("reports:report_detail", args=[self.report.id])
        kept_url = reverse("reports:report_detail", args=[kept.id])
        self.login_as_creator()

        self.client.post(self.recover_url())

        list_response = self.client.get(reverse("reports:report_list"))
        self.assertNotContains(list_response, recovered_url)
        self.assertContains(list_response, kept_url)

        search_response = self.client.get(
            reverse("reports:report_list"),
            {"q": "calculator"},
        )
        self.assertNotContains(search_response, recovered_url)

    # Given a Recovered report, when a user attempts to use the Contact
    # Reporter function, then the system prevents the action.
    def test_recovered_report_cannot_be_contacted(self):
        contact_url = reverse("reports:contact_reporter", args=[self.report.id])
        self.login_as_creator()
        self.client.post(self.recover_url())

        self.client.login(
            username=self.other_user.email,
            password="StrongPass123",
        )

        self.assertEqual(self.client.get(contact_url).status_code, 404)
        self.assertEqual(
            self.client.post(contact_url, {"message": "Hello"}).status_code,
            404,
        )

    # Given that the user cancels the confirmation, when the confirmation page
    # closes, then the report remains Active.
    def test_opening_the_confirmation_page_does_not_change_the_status(self):
        self.login_as_creator()

        response = self.client.get(self.recover_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Mark this item as recovered?")
        self.assertContains(response, self.report.title)

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.ACTIVE)
        self.assertIsNone(self.report.recovered_at)

    # Given a successful status change, when the report is saved, then the
    # system records the date and time of the recovery.
    def test_recovery_timestamp_is_recorded(self):
        before = timezone.now()
        self.login_as_creator()

        self.client.post(self.recover_url())

        self.report.refresh_from_db()
        self.assertIsNotNone(self.report.recovered_at)
        self.assertGreaterEqual(self.report.recovered_at, before)
        self.assertLessEqual(self.report.recovered_at, timezone.now())

    # Given a Recovered report, when its creator opens the report history, then
    # the report is displayed with the Recovered status. La pantalla llega con
    # RF16; aqui se verifica que el dato que esa pantalla necesita queda listo.
    def test_recovered_report_stays_available_for_its_creator(self):
        self.login_as_creator()

        self.client.post(self.recover_url())

        own_reports = ItemReport.objects.filter(creator=self.creator)
        self.assertTrue(own_reports.filter(id=self.report.id).exists())
        self.assertEqual(
            own_reports.get(id=self.report.id).get_status_display(),
            "Recovered",
        )

    def test_recovering_does_not_change_the_creator_or_the_content(self):
        self.login_as_creator()

        self.client.post(self.recover_url())

        self.report.refresh_from_db()
        self.assertEqual(self.report.creator, self.creator)
        self.assertEqual(self.report.title, "Lost calculator")
        self.assertEqual(self.report.report_type, ItemReport.ReportType.LOST)

    def test_recover_button_is_shown_only_to_the_creator(self):
        detail_url = reverse("reports:report_detail", args=[self.report.id])

        self.login_as_creator()
        self.assertContains(self.client.get(detail_url), self.recover_url())

        self.client.login(
            username=self.other_user.email,
            password="StrongPass123",
        )
        self.assertNotContains(self.client.get(detail_url), self.recover_url())

    def test_recovered_report_can_still_be_edited_and_deleted_by_its_creator(self):
        self.login_as_creator()
        self.client.post(self.recover_url())

        edit_url = reverse("reports:edit_report", args=[self.report.id])
        delete_url = reverse("reports:delete_report", args=[self.report.id])

        self.assertEqual(self.client.get(edit_url).status_code, 200)
        self.assertEqual(self.client.get(delete_url).status_code, 200)
