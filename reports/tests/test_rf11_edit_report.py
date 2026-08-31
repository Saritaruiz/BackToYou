"""RF11 - Edit Report. Un test por criterio de aceptacion."""

import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Category, ItemReport

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
    b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


class EditReportTests(TestCase):
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
        self.other_category = Category.objects.create(name="Documents")

    def create_report(self, status=ItemReport.Status.ACTIVE):
        return ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=status,
        )

    def valid_payload(self, **overrides):
        payload = {
            "title": "Lost calculator (updated)",
            "description": "Black scientific calculator with a name tag",
            "category": self.other_category.id,
            "event_date": "2026-08-11",
            "location": "Block 38",
        }
        payload.update(overrides)
        return payload

    def login_as_creator(self):
        self.client.login(username=self.creator.email, password="StrongPass123")

    # Given that the authenticated user is the report creator, when the user
    # submits valid changes, then the system updates the report.
    def test_creator_can_update_their_own_report(self):
        report = self.create_report()
        self.login_as_creator()

        response = self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        self.assertRedirects(
            response,
            reverse("reports:report_detail", args=[report.id]),
        )

        report.refresh_from_db()
        self.assertEqual(report.title, "Lost calculator (updated)")
        self.assertEqual(
            report.description,
            "Black scientific calculator with a name tag",
        )
        self.assertEqual(report.category, self.other_category)
        self.assertEqual(str(report.event_date), "2026-08-11")
        self.assertEqual(report.location, "Block 38")

    # Given that the authenticated user is not the report creator, when the
    # user attempts to edit the report, then the system denies the action.
    def test_other_user_cannot_edit_the_report(self):
        report = self.create_report()
        self.client.login(
            username=self.other_user.email,
            password="StrongPass123",
        )

        get_response = self.client.get(
            reverse("reports:edit_report", args=[report.id])
        )
        post_response = self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)

        report.refresh_from_db()
        self.assertEqual(report.title, "Lost calculator")

    def test_anonymous_user_is_redirected_to_login(self):
        report = self.create_report()

        response = self.client.get(
            reverse("reports:edit_report", args=[report.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    # Given one or more invalid or empty required fields, when the user submits
    # the changes, then the system prevents the update and identifies the
    # invalid fields.
    def test_empty_required_field_prevents_the_update(self):
        report = self.create_report()
        self.login_as_creator()

        response = self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(title=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "title", "This field is required.")

        report.refresh_from_db()
        self.assertEqual(report.title, "Lost calculator")

    def test_invalid_event_date_prevents_the_update(self):
        report = self.create_report()
        self.login_as_creator()

        response = self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(event_date="not-a-date"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["event_date"])

        report.refresh_from_db()
        self.assertEqual(str(report.event_date), "2026-08-10")

    # Given an Active report, when the creator edits it, then the report
    # remains Active and does not return to Pending Review.
    def test_active_report_stays_active_after_editing(self):
        report = self.create_report(status=ItemReport.Status.ACTIVE)
        self.login_as_creator()

        self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.ACTIVE)

    # Given a Pending Review report, when the creator edits it, then the report
    # remains Pending Review.
    def test_pending_review_report_stays_pending_after_editing(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_creator()

        response = self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        self.assertRedirects(response, reverse("reports:report_list"))

        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)
        self.assertEqual(report.title, "Lost calculator (updated)")

    # Given a Recovered report, when the creator edits its information, then
    # the report remains Recovered.
    def test_recovered_report_stays_recovered_after_editing(self):
        report = self.create_report(status=ItemReport.Status.RECOVERED)
        self.login_as_creator()

        self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.RECOVERED)
        self.assertEqual(report.title, "Lost calculator (updated)")

    # Given a Rejected report, when the creator attempts to edit it, then the
    # system denies the action.
    def test_rejected_report_cannot_be_edited(self):
        report = self.create_report(status=ItemReport.Status.REJECTED)
        self.login_as_creator()

        get_response = self.client.get(
            reverse("reports:edit_report", args=[report.id])
        )
        post_response = self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)

        report.refresh_from_db()
        self.assertEqual(report.title, "Lost calculator")

    # Given a successful update, when the report is saved, then the system
    # records the date and time of the modification.
    def test_update_records_the_modification_timestamp(self):
        report = self.create_report()
        original_updated_at = report.updated_at
        original_created_at = report.created_at
        self.login_as_creator()

        self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        report.refresh_from_db()
        self.assertGreater(report.updated_at, original_updated_at)
        self.assertEqual(report.created_at, original_created_at)

    def test_edit_does_not_change_the_creator_or_the_report_type(self):
        report = self.create_report()
        self.login_as_creator()

        self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.valid_payload(),
        )

        report.refresh_from_db()
        self.assertEqual(report.creator, self.creator)
        self.assertEqual(report.report_type, ItemReport.ReportType.LOST)

    def test_edit_form_is_prefilled_with_the_current_information(self):
        report = self.create_report()
        self.login_as_creator()

        response = self.client.get(
            reverse("reports:edit_report", args=[report.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lost calculator")
        self.assertContains(response, "Library")

    def test_edit_button_is_shown_only_to_the_creator(self):
        report = self.create_report()
        edit_url = reverse("reports:edit_report", args=[report.id])
        detail_url = reverse("reports:report_detail", args=[report.id])

        self.login_as_creator()
        self.assertContains(self.client.get(detail_url), edit_url)

        self.client.login(
            username=self.other_user.email,
            password="StrongPass123",
        )
        self.assertNotContains(self.client.get(detail_url), edit_url)


class EditReportImageTests(TestCase):
    """Los tests de imagen escriben en un MEDIA_ROOT temporal."""

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
        self.report = ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
            image=SimpleUploadedFile(
                "original.png",
                PNG_BYTES,
                content_type="image/png",
            ),
        )
        self.client.login(
            username=self.creator.email,
            password="StrongPass123",
        )

    def payload(self, **overrides):
        payload = {
            "title": "Lost calculator",
            "description": "Black scientific calculator",
            "category": self.category.id,
            "event_date": "2026-08-10",
            "location": "Library",
        }
        payload.update(overrides)
        return payload

    # Given a report with an attached image, when the creator replaces the
    # image with a valid one, then the system stores the new image and the
    # report keeps a single associated image.
    def test_replacing_the_image_keeps_a_single_image(self):
        original_name = self.report.image.name

        response = self.client.post(
            reverse("reports:edit_report", args=[self.report.id]),
            self.payload(
                image=SimpleUploadedFile(
                    "replacement.png",
                    PNG_BYTES,
                    content_type="image/png",
                )
            ),
        )

        self.assertRedirects(
            response,
            reverse("reports:report_detail", args=[self.report.id]),
        )

        self.report.refresh_from_db()
        self.assertNotEqual(self.report.image.name, original_name)
        self.assertIn("replacement", self.report.image.name)
        self.assertTrue(self.report.image.name.startswith("reports/"))

    def test_editing_without_uploading_keeps_the_existing_image(self):
        original_name = self.report.image.name

        self.client.post(
            reverse("reports:edit_report", args=[self.report.id]),
            self.payload(title="Lost calculator (updated)"),
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.image.name, original_name)
        self.assertEqual(self.report.title, "Lost calculator (updated)")

    def test_unsupported_image_format_is_rejected(self):
        original_name = self.report.image.name

        response = self.client.post(
            reverse("reports:edit_report", args=[self.report.id]),
            self.payload(
                image=SimpleUploadedFile(
                    "item.gif",
                    b"GIF89a",
                    content_type="image/gif",
                )
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["image"])

        self.report.refresh_from_db()
        self.assertEqual(self.report.image.name, original_name)
