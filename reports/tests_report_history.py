"""RF16 - Report History. Un test por criterio de aceptacion."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, ItemReport


class ReportHistoryTests(TestCase):
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
        self.url = reverse("reports:my_reports")

    def create_report(self, title, status=ItemReport.Status.ACTIVE, creator=None):
        return ItemReport.objects.create(
            title=title,
            description="Item description",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=creator or self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=status,
        )

    def login_as_creator(self):
        self.client.login(username=self.creator.email, password="StrongPass123")

    # Given an authenticated user who has created reports, when the user opens
    # the My Reports section, then the system displays all reports associated
    # with that user.
    def test_history_shows_every_report_of_the_authenticated_user(self):
        first = self.create_report("Lost calculator")
        second = self.create_report("Found wallet")
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, first.title)
        self.assertContains(response, second.title)
        self.assertEqual(len(response.context["reports"]), 2)

    # Given reports with different statuses, when the report history is
    # displayed, then the system shows the current status of each report.
    # Given a report with Pending Review, Active, Recovered, or Rejected
    # status, then it is displayed with the corresponding status.
    def test_history_shows_the_current_status_of_every_report(self):
        statuses = {
            ItemReport.Status.PENDING_REVIEW: "Pending Review",
            ItemReport.Status.ACTIVE: "Active",
            ItemReport.Status.RECOVERED: "Recovered",
            ItemReport.Status.REJECTED: "Rejected",
        }
        for status in statuses:
            self.create_report(f"Report {status}", status=status)
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertEqual(len(response.context["reports"]), 4)
        for status, label in statuses.items():
            self.assertContains(response, f"Report {status}")
            self.assertContains(response, f'<span class="status-pill">{label}</span>', html=False)

    # Given an authenticated user, when the report history is displayed, then
    # the system does not include reports created by other users.
    def test_history_excludes_reports_created_by_other_users(self):
        mine = self.create_report("My report")
        theirs = self.create_report("Their report", creator=self.other_user)
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertContains(response, mine.title)
        self.assertNotContains(response, theirs.title)
        self.assertEqual(
            list(response.context["reports"]),
            [mine],
        )

    # Given several reports, when the history is displayed, then the reports
    # are ordered from most recent to oldest.
    def test_history_is_ordered_from_most_recent_to_oldest(self):
        oldest = self.create_report("Oldest report")
        middle = self.create_report("Middle report")
        newest = self.create_report("Newest report")
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertEqual(
            list(response.context["reports"]),
            [newest, middle, oldest],
        )

    # Given a user who has not created any reports, when the user opens the My
    # Reports section, then the system displays an informative empty state.
    def test_empty_state_is_shown_when_the_user_has_no_reports(self):
        self.create_report("Their report", creator=self.other_user)
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["reports"]), 0)
        self.assertContains(response, "You have not created any reports yet.")
        self.assertContains(response, reverse("reports:create_lost_report"))

    # Given an unauthenticated visitor, when they attempt to open the My
    # Reports section, then the system redirects them to the login page.
    def test_anonymous_visitor_is_redirected_to_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    # Given a report displayed in the history, when the user selects it, then
    # the system shows the actions authorized for the creator of that report.
    def test_active_report_offers_details_edit_recover_and_delete(self):
        report = self.create_report("Active report", status=ItemReport.Status.ACTIVE)
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertContains(response, reverse("reports:report_detail", args=[report.id]))
        self.assertContains(response, reverse("reports:edit_report", args=[report.id]))
        self.assertContains(
            response,
            reverse("reports:mark_report_recovered", args=[report.id]),
        )
        self.assertContains(response, reverse("reports:delete_report", args=[report.id]))

    def test_pending_report_offers_edit_and_delete_but_not_recover(self):
        report = self.create_report(
            "Pending report",
            status=ItemReport.Status.PENDING_REVIEW,
        )
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertContains(response, reverse("reports:edit_report", args=[report.id]))
        self.assertContains(response, reverse("reports:delete_report", args=[report.id]))
        self.assertNotContains(
            response,
            reverse("reports:mark_report_recovered", args=[report.id]),
        )

    def test_recovered_report_offers_edit_and_delete_but_not_recover(self):
        report = self.create_report(
            "Recovered report",
            status=ItemReport.Status.RECOVERED,
        )
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertContains(response, reverse("reports:edit_report", args=[report.id]))
        self.assertContains(response, reverse("reports:delete_report", args=[report.id]))
        self.assertNotContains(
            response,
            reverse("reports:mark_report_recovered", args=[report.id]),
        )

    def test_rejected_report_offers_only_delete(self):
        report = self.create_report(
            "Rejected report",
            status=ItemReport.Status.REJECTED,
        )
        self.login_as_creator()

        response = self.client.get(self.url)

        self.assertContains(response, reverse("reports:delete_report", args=[report.id]))
        self.assertNotContains(response, reverse("reports:edit_report", args=[report.id]))
        self.assertNotContains(
            response,
            reverse("reports:mark_report_recovered", args=[report.id]),
        )

    # Postcondition: no report information is modified by viewing the history.
    def test_viewing_the_history_does_not_modify_any_report(self):
        report = self.create_report("Lost calculator")
        before_status = report.status
        before_updated_at = report.updated_at
        self.login_as_creator()

        self.client.get(self.url)

        report.refresh_from_db()
        self.assertEqual(report.status, before_status)
        self.assertEqual(report.updated_at, before_updated_at)

    def test_nav_shows_the_my_reports_link_only_to_authenticated_users(self):
        anonymous_response = self.client.get(reverse("reports:report_list"))
        self.assertNotContains(anonymous_response, self.url)

        self.login_as_creator()
        authenticated_response = self.client.get(reverse("reports:report_list"))
        self.assertContains(authenticated_response, self.url)
