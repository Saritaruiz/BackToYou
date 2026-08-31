"""RF18 - View Report Details. Un test por criterio de aceptacion."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, ItemReport

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
    b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


class ViewReportDetailsTests(TestCase):
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

    def create_report(self, status=ItemReport.Status.ACTIVE, creator=None):
        return ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator with a name tag",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=creator or self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=status,
        )

    def detail_url(self, report):
        return reverse("reports:report_detail", args=[report.id])

    def login_as(self, user):
        self.client.login(username=user.email, password="StrongPass123")

    # Given an Active report selected from the public report list, when the
    # user opens it, then the system displays its complete information.
    def test_active_report_shows_its_complete_information(self):
        report = self.create_report()

        response = self.client.get(self.detail_url(report))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, report.title)
        self.assertContains(response, report.description)
        self.assertContains(response, report.category.name)
        self.assertContains(response, report.location)
        self.assertContains(response, "Lost")
        self.assertContains(response, "Active")

    # Given a report selected by its creator from the My Reports section, when
    # the creator opens it, then the system displays its complete information
    # and current status.
    def test_creator_can_open_their_report_in_any_status(self):
        self.login_as(self.creator)

        for status, label in (
            (ItemReport.Status.PENDING_REVIEW, "Pending Review"),
            (ItemReport.Status.ACTIVE, "Active"),
            (ItemReport.Status.RECOVERED, "Recovered"),
            (ItemReport.Status.REJECTED, "Rejected"),
        ):
            report = self.create_report(status=status)

            response = self.client.get(self.detail_url(report))

            self.assertEqual(response.status_code, 200)
            self.assertContains(response, report.title)
            self.assertContains(response, report.description)
            self.assertContains(response, label)

    # Given a report with Pending Review or Rejected status, when a user who is
    # not its creator attempts to open it, then the system denies access.
    def test_unpublished_reports_are_denied_to_everyone_but_their_creator(self):
        for status in (
            ItemReport.Status.PENDING_REVIEW,
            ItemReport.Status.REJECTED,
            ItemReport.Status.RECOVERED,
        ):
            report = self.create_report(status=status)

            anonymous = self.client.get(self.detail_url(report))
            self.assertEqual(anonymous.status_code, 404)

            self.login_as(self.other_user)
            other = self.client.get(self.detail_url(report))
            self.assertEqual(other.status_code, 404)
            self.client.logout()

    # Given a report that does not exist or is unavailable to the user, when
    # the user attempts to open it, then the system displays an informative
    # message.
    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_missing_report_shows_the_informative_page(self):
        missing_url = reverse("reports:report_detail", args=[9999])

        response = self.client.get(missing_url)

        self.assertEqual(response.status_code, 404)
        self.assertContains(
            response,
            "This report is not available",
            status_code=404,
        )

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_unavailable_report_shows_the_informative_page(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)

        response = self.client.get(self.detail_url(report))

        self.assertEqual(response.status_code, 404)
        self.assertContains(
            response,
            "This report is not available",
            status_code=404,
        )

    # Given an Active report created by another user, when its details are
    # displayed, then the Contact Reporter action is available.
    def test_contact_action_is_offered_on_another_users_active_report(self):
        report = self.create_report()
        contact_url = reverse("reports:contact_reporter", args=[report.id])
        self.login_as(self.other_user)

        response = self.client.get(self.detail_url(report))

        self.assertContains(response, contact_url)
        self.assertTrue(response.context["can_contact_reporter"])

    # Given a report owned by the authenticated user, when its details are
    # displayed, then the actions authorized for the creator are available.
    def test_creator_sees_their_authorized_actions_per_status(self):
        self.login_as(self.creator)

        expected = {
            ItemReport.Status.ACTIVE: (True, True, True),
            ItemReport.Status.PENDING_REVIEW: (True, True, False),
            ItemReport.Status.RECOVERED: (True, True, False),
            ItemReport.Status.REJECTED: (False, True, False),
        }

        for status, (can_edit, can_delete, can_recover) in expected.items():
            report = self.create_report(status=status)

            response = self.client.get(self.detail_url(report))

            self.assertEqual(response.context["can_edit_report"], can_edit, status)
            self.assertEqual(response.context["can_delete_report"], can_delete, status)
            self.assertEqual(response.context["can_mark_recovered"], can_recover, status)
            self.assertFalse(response.context["can_contact_reporter"], status)

            edit_url = reverse("reports:edit_report", args=[report.id])
            if can_edit:
                self.assertContains(response, edit_url)
            else:
                self.assertNotContains(response, edit_url)

    # Given an unauthenticated visitor, when they open an Active report, then
    # the report information is displayed but Contact Reporter is not
    # available.
    def test_anonymous_visitor_sees_the_report_but_not_the_contact_action(self):
        report = self.create_report()
        contact_url = reverse("reports:contact_reporter", args=[report.id])

        response = self.client.get(self.detail_url(report))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, report.title)
        self.assertNotContains(response, contact_url)
        self.assertFalse(response.context["can_contact_reporter"])

    def test_creator_does_not_see_the_contact_action_on_their_own_report(self):
        report = self.create_report()
        contact_url = reverse("reports:contact_reporter", args=[report.id])
        self.login_as(self.creator)

        response = self.client.get(self.detail_url(report))

        self.assertNotContains(response, contact_url)

    def test_creator_is_sent_back_to_the_report_history(self):
        report = self.create_report()

        self.login_as(self.creator)
        creator_response = self.client.get(self.detail_url(report))
        self.assertContains(creator_response, reverse("reports:my_reports"))

        self.login_as(self.other_user)
        other_response = self.client.get(self.detail_url(report))
        self.assertContains(other_response, reverse("reports:report_list"))

    def test_history_links_every_report_to_its_details(self):
        reports = [
            self.create_report(status=status)
            for status in (
                ItemReport.Status.PENDING_REVIEW,
                ItemReport.Status.ACTIVE,
                ItemReport.Status.RECOVERED,
                ItemReport.Status.REJECTED,
            )
        ]
        self.login_as(self.creator)

        response = self.client.get(reverse("reports:my_reports"))

        for report in reports:
            self.assertContains(response, self.detail_url(report))

    # Postcondition: no report information is modified by viewing its details.
    def test_viewing_the_details_does_not_modify_the_report(self):
        report = self.create_report()
        before_status = report.status
        before_updated_at = report.updated_at

        self.login_as(self.creator)
        self.client.get(self.detail_url(report))

        report.refresh_from_db()
        self.assertEqual(report.status, before_status)
        self.assertEqual(report.updated_at, before_updated_at)

    # Given a report without an available image, when the details are
    # displayed, then the remaining information is still shown.
    def test_report_without_image_still_shows_its_information(self):
        report = self.create_report()

        response = self.client.get(self.detail_url(report))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="report-image detail"')
        self.assertContains(response, report.description)
        self.assertContains(response, report.location)


class ReportDetailsImageTests(TestCase):
    """El test de imagen escribe en un MEDIA_ROOT temporal."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        self.creator = User.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")

    # Given a report with an attached image, when the details are displayed,
    # then the corresponding image is shown.
    def test_attached_image_is_displayed(self):
        report = ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
            image=SimpleUploadedFile("item.png", PNG_BYTES, content_type="image/png"),
        )

        response = self.client.get(
            reverse("reports:report_detail", args=[report.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="report-image detail"')
        self.assertContains(response, report.image.url)
