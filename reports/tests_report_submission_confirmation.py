"""RF17 - Report Submission Confirmation."""

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Category, ItemReport


CONFIRMATION_MESSAGE = (
    "Report submitted successfully. It is currently Pending Review and will "
    "become publicly visible after administrator approval."
)


class ReportSubmissionConfirmationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="reporter@eafit.edu.co",
            email="reporter@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")
        self.client.login(username=self.user.email, password="StrongPass123")

    def valid_payload(self, **overrides):
        payload = {
            "title": "Lost calculator",
            "description": "Black scientific calculator",
            "category": self.category.id,
            "event_date": "2026-08-10",
            "location": "Library",
        }
        payload.update(overrides)
        return payload

    def messages_for(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]

    def assert_no_success_confirmation(self, response):
        self.assertNotIn(CONFIRMATION_MESSAGE, self.messages_for(response))

    def test_successful_lost_report_creation_shows_submission_confirmation(self):
        response = self.client.post(
            reverse("reports:create_lost_report"),
            self.valid_payload(),
            follow=True,
        )

        self.assertContains(response, CONFIRMATION_MESSAGE)
        self.assertContains(response, "Pending Review")
        self.assertContains(response, "administrator approval")

    def test_successful_found_report_creation_shows_submission_confirmation(self):
        response = self.client.post(
            reverse("reports:create_found_report"),
            self.valid_payload(title="Found wallet", location="Block 38"),
            follow=True,
        )

        self.assertContains(response, CONFIRMATION_MESSAGE)
        self.assertContains(response, "Pending Review")
        self.assertContains(response, "administrator approval")

    def test_lost_report_is_saved_as_pending_review_with_creator_and_type(self):
        self.client.post(reverse("reports:create_lost_report"), self.valid_payload())

        report = ItemReport.objects.get(title="Lost calculator")
        self.assertEqual(report.creator, self.user)
        self.assertEqual(report.report_type, ItemReport.ReportType.LOST)
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)

    def test_found_report_is_saved_as_pending_review_with_creator_and_type(self):
        self.client.post(
            reverse("reports:create_found_report"),
            self.valid_payload(title="Found wallet"),
        )

        report = ItemReport.objects.get(title="Found wallet")
        self.assertEqual(report.creator, self.user)
        self.assertEqual(report.report_type, ItemReport.ReportType.FOUND)
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)

    def test_invalid_lost_form_does_not_show_success_or_create_report(self):
        response = self.client.post(
            reverse("reports:create_lost_report"),
            self.valid_payload(title=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "title", "This field is required.")
        self.assert_no_success_confirmation(response)
        self.assertFalse(ItemReport.objects.exists())

    def test_invalid_found_form_does_not_show_success_or_create_report(self):
        response = self.client.post(
            reverse("reports:create_found_report"),
            self.valid_payload(title=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "title", "This field is required.")
        self.assert_no_success_confirmation(response)
        self.assertFalse(ItemReport.objects.exists())

    def test_invalid_image_submission_does_not_show_success_or_create_report(self):
        response = self.client.post(
            reverse("reports:create_lost_report"),
            self.valid_payload(
                image=SimpleUploadedFile(
                    "item.gif",
                    b"GIF89a",
                    content_type="image/gif",
                )
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["image"])
        self.assert_no_success_confirmation(response)
        self.assertFalse(ItemReport.objects.exists())

    def test_newly_submitted_pending_review_report_is_hidden_from_public_list(self):
        self.client.post(reverse("reports:create_lost_report"), self.valid_payload())

        response = self.client.get(reverse("reports:report_list"))

        self.assertNotContains(response, "Lost calculator")

    def test_newly_submitted_report_remains_available_in_creator_history(self):
        self.client.post(reverse("reports:create_lost_report"), self.valid_payload())

        response = self.client.get(reverse("reports:my_reports"))

        self.assertContains(response, "Lost calculator")
        self.assertContains(response, "Pending Review")
