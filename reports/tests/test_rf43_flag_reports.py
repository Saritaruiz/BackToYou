"""RF43 - Flag Inappropriate Reports. Un test por criterio de aceptacion."""

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from ..models import Category, ItemReport, ReportFlag


PASSWORD = "StrongPass123"


class FlagReportTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.creator = self.create_user("creator@eafit.edu.co")
        self.member = self.create_user("member@eafit.edu.co")
        self.other_member = self.create_user("other@eafit.edu.co")
        self.admin = self.create_user("admin@eafit.edu.co", role=User.Role.ADMINISTRATOR)
        self.category = Category.objects.create(name="Keys")
        self.report = self.create_report()

    def create_user(self, email, **extra):
        return get_user_model().objects.create_user(
            username=email, email=email, password=PASSWORD, **extra,
        )

    def create_report(self, title="House keys", status=ItemReport.Status.ACTIVE):
        return ItemReport.objects.create(
            title=title,
            description="Three keys on a green keyring",
            category=self.category,
            event_date="2026-10-05",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.FOUND,
            status=status,
        )

    def login(self, user):
        self.client.login(username=user.email, password=PASSWORD)

    def flag_url(self, report=None):
        return reverse("reports:flag_report", args=[(report or self.report).id])

    def detail_url(self, report=None):
        return reverse("reports:report_detail", args=[(report or self.report).id])

    def add_flag(self, user, reason=ReportFlag.Reason.PERSONAL_DATA, details=""):
        return ReportFlag.objects.create(
            report=self.report, flagged_by=user, reason=reason, details=details,
        )


class FlagReportTests(FlagReportTestCase):
    # Given an Active report from another user, when a logged-in user flags it
    # and chooses a reason, then the system saves the flag and confirms that it
    # was sent.
    def test_member_flags_an_active_report_with_a_reason(self):
        self.login(self.member)

        response = self.client.post(
            self.flag_url(),
            {"reason": ReportFlag.Reason.PERSONAL_DATA, "details": "  The photo shows a student ID.  "},
            follow=True,
        )

        self.assertRedirects(response, self.detail_url())
        self.assertContains(response, "The report was flagged and an administrator will review it.")
        flag = ReportFlag.objects.get()
        self.assertEqual(flag.report, self.report)
        self.assertEqual(flag.flagged_by, self.member)
        self.assertEqual(flag.reason, ReportFlag.Reason.PERSONAL_DATA)
        self.assertEqual(flag.details, "The photo shows a student ID.")
        self.assertIsNone(flag.reviewed_at)

    def test_detail_page_offers_the_flag_option(self):
        self.login(self.member)

        response = self.client.get(self.detail_url())

        self.assertContains(response, self.flag_url())

    def test_flag_requires_a_valid_reason(self):
        self.login(self.member)

        missing = self.client.post(self.flag_url(), {"details": "Looks fake"})
        invalid = self.client.post(self.flag_url(), {"reason": "SPAM"})

        self.assertContains(missing, "Choose a reason for flagging this report.")
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(ReportFlag.objects.exists())

    # Given a report the user already flagged, when they try to flag it again,
    # then the system does not create a duplicate flag.
    def test_flagging_twice_does_not_create_a_duplicate(self):
        self.add_flag(self.member)
        self.login(self.member)

        response = self.client.post(
            self.flag_url(), {"reason": ReportFlag.Reason.OFFENSIVE}, follow=True,
        )

        self.assertRedirects(response, self.detail_url())
        self.assertContains(response, "You already flagged this report.")
        self.assertEqual(ReportFlag.objects.count(), 1)

    def test_detail_page_tells_the_member_they_already_flagged(self):
        self.add_flag(self.member)
        self.login(self.member)

        response = self.client.get(self.detail_url())

        self.assertContains(response, "You flagged this report.")
        self.assertNotContains(response, self.flag_url())

    # Given the user's own report, when they view it, then the flag option is
    # not available.
    def test_creator_cannot_flag_their_own_report(self):
        self.login(self.creator)

        detail = self.client.get(self.detail_url())
        response = self.client.post(self.flag_url(), {"reason": ReportFlag.Reason.OTHER})

        self.assertNotContains(detail, self.flag_url())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ReportFlag.objects.exists())

    def test_visitor_must_log_in_to_flag(self):
        detail = self.client.get(self.detail_url())
        response = self.client.get(self.flag_url())

        self.assertNotContains(detail, self.flag_url())
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.flag_url()}")

    def test_only_published_reports_can_be_flagged(self):
        pending = self.create_report("Pending keys", ItemReport.Status.PENDING_REVIEW)
        recovered = self.create_report("Recovered keys", ItemReport.Status.RECOVERED)
        self.login(self.member)

        for report in (pending, recovered):
            with self.subTest(status=report.status):
                response = self.client.post(self.flag_url(report), {"reason": ReportFlag.Reason.OTHER})
                self.assertEqual(response.status_code, 404)
        self.assertFalse(ReportFlag.objects.exists())

    # Given a flagged report, when other users view it, then they cannot see
    # who flagged it.
    def test_nobody_else_sees_who_flagged_the_report(self):
        self.add_flag(self.member, details="Personal data in the photo")

        for viewer in (self.creator, self.other_member, None):
            with self.subTest(viewer=viewer):
                self.client.logout()
                if viewer:
                    self.login(viewer)
                response = self.client.get(self.detail_url())
                self.assertNotContains(response, self.member.email)
                self.assertNotContains(response, "You flagged this report.")
                self.assertNotContains(response, "Personal data in the photo")


class FlaggedReportsAdministrationTests(FlagReportTestCase):
    def setUp(self):
        super().setUp()
        self.add_flag(self.member, ReportFlag.Reason.PERSONAL_DATA, "Shows a student ID")
        self.add_flag(self.other_member, ReportFlag.Reason.PERSONAL_DATA)
        self.login(self.admin)

    def review_url(self):
        return reverse("administration_flagged_report", args=[self.report.id])

    def remove_url(self):
        return reverse("administration_flagged_report_remove", args=[self.report.id])

    # Given flagged reports, when an Administrator opens the administration
    # panel, then they see the list of flagged reports with the number of
    # flags and their reasons.
    def test_administrator_sees_flagged_reports_with_count_and_reasons(self):
        quiet = self.create_report("Blue umbrella")
        offensive = self.create_report("Black wallet")
        ReportFlag.objects.create(report=offensive, flagged_by=self.member, reason=ReportFlag.Reason.OFFENSIVE)

        panel = self.client.get(reverse("administration"))
        response = self.client.get(reverse("administration_flagged_reports"))

        self.assertContains(panel, reverse("administration_flagged_reports"))
        self.assertContains(panel, "2 waiting for review.")
        self.assertEqual(
            [report.title for report in response.context["reports"]],
            ["House keys", "Black wallet"],
        )
        self.assertNotContains(response, quiet.title)
        self.assertContains(response, "<strong>2</strong>", html=False)
        self.assertContains(response, "Personal data ×2")
        self.assertContains(response, "Offensive content")

    def test_review_page_lists_each_flag_with_its_reason_and_details(self):
        response = self.client.get(self.review_url())

        self.assertContains(response, "2 flags")
        self.assertContains(response, "Shows a student ID")
        self.assertContains(response, "Personal data", count=2)

    def test_regular_user_cannot_open_flagged_reports(self):
        self.client.logout()
        self.login(self.member)

        for url in (reverse("administration_flagged_reports"), self.review_url(), self.remove_url()):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    # Given a flagged report, when an Administrator reviews it, then they can
    # dismiss the flags or remove the report from public view.
    def test_administrator_dismisses_the_flags_and_the_report_stays_public(self):
        response = self.client.post(self.review_url(), {"action": "dismiss"}, follow=True)

        self.assertRedirects(response, reverse("administration_flagged_reports"))
        self.assertContains(response, "The flags were dismissed. The report stays public.")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.ACTIVE)
        self.assertFalse(ReportFlag.objects.filter(reviewed_at__isnull=True).exists())
        self.assertEqual(set(ReportFlag.objects.values_list("reviewed_by", flat=True)), {self.admin.id})
        self.assertNotContains(response, "House keys")
        self.assertEqual(len(mail.outbox), 0)

    def test_administrator_removes_the_report_from_public_view(self):
        response = self.client.post(self.remove_url(), follow=True)

        self.assertRedirects(response, reverse("administration_flagged_reports"))
        self.assertContains(response, "Report &quot;House keys&quot; was removed from public view.")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.REJECTED)
        self.assertEqual(self.report.moderated_by, self.admin)
        self.assertIsNotNone(self.report.moderated_at)
        self.assertFalse(ReportFlag.objects.filter(reviewed_at__isnull=True).exists())
        public = self.client.get(reverse("reports:report_list"))
        self.assertNotContains(public, "House keys")

    def test_removed_report_creator_gets_the_reasons_but_not_who_flagged(self):
        self.client.post(self.remove_url())

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.creator.email])
        self.assertIn("removed from public view", email.subject)
        self.assertIn("Reason: Personal data", email.body)
        self.assertNotIn(self.member.email, email.body)
        self.assertNotIn(self.other_member.email, email.body)

    def test_opening_the_removal_confirmation_changes_nothing(self):
        response = self.client.get(self.remove_url())

        self.assertContains(response, "Remove this report from public view?")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.ACTIVE)
        self.assertEqual(ReportFlag.objects.filter(reviewed_at__isnull=True).count(), 2)

    def test_reviewed_report_is_no_longer_waiting(self):
        self.client.post(self.review_url(), {"action": "dismiss"})

        self.assertEqual(self.client.get(self.review_url()).status_code, 404)
        self.assertEqual(self.client.post(self.remove_url()).status_code, 404)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.ACTIVE)

    def test_invalid_review_action_changes_nothing(self):
        response = self.client.post(self.review_url(), {"action": "approve"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(ReportFlag.objects.filter(reviewed_at__isnull=True).count(), 2)

    def test_flagged_list_queries_do_not_grow_with_reports(self):
        for number in range(5):
            report = self.create_report(f"Wallet {number}")
            ReportFlag.objects.create(report=report, flagged_by=self.member, reason=ReportFlag.Reason.OTHER)

        url = reverse("administration_flagged_reports")
        self.client.get(url)
        with self.assertNumQueries(4):
            self.client.get(url)
