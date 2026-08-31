from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from ..models import Category, ContactMessage, ItemReport


class ReportCreationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reporter@eafit.edu.co",
            email="reporter@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")

    def test_lost_report_creation_requires_authentication(self):
        response = self.client.get(reverse("reports:create_lost_report"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_lost_report_creation_sets_type_status_and_creator(self):
        self.client.login(username=self.user.email, password="StrongPass123")

        response = self.client.post(
            reverse("reports:create_lost_report"),
            {
                "title": "Lost calculator",
                "description": "Black scientific calculator",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Library",
            },
        )

        self.assertRedirects(response, reverse("reports:report_list"))
        report = ItemReport.objects.get(title="Lost calculator")
        self.assertEqual(report.report_type, ItemReport.ReportType.LOST)
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)
        self.assertEqual(report.creator, self.user)

    def test_found_report_creation_sets_found_type(self):
        self.client.login(username=self.user.email, password="StrongPass123")

        self.client.post(
            reverse("reports:create_found_report"),
            {
                "title": "Found keys",
                "description": "Keys with blue keychain",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Block 38",
            },
        )

        report = ItemReport.objects.get(title="Found keys")
        self.assertEqual(report.report_type, ItemReport.ReportType.FOUND)
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)

    def test_optional_image_upload_is_saved_with_report(self):
        self.client.login(username=self.user.email, password="StrongPass123")
        image = SimpleUploadedFile(
            "item.png",
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
                b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
                b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
            content_type="image/png",
        )

        response = self.client.post(
            reverse("reports:create_lost_report"),
            {
                "title": "Lost notebook",
                "description": "Notebook with stickers",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Cafeteria",
                "image": image,
            },
        )

        self.assertRedirects(response, reverse("reports:report_list"))
        report = ItemReport.objects.get(title="Lost notebook")
        self.assertTrue(report.image.name.startswith("reports/"))

    def test_pending_reports_do_not_appear_in_public_list_or_detail(self):
        pending = ItemReport.objects.create(
            title="Pending report",
            description="Not approved yet",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.user,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.PENDING_REVIEW,
        )
        active = ItemReport.objects.create(
            title="Active report",
            description="Approved",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.user,
            report_type=ItemReport.ReportType.FOUND,
            status=ItemReport.Status.ACTIVE,
        )

        response = self.client.get(reverse("reports:report_list"))
        self.assertContains(response, active.title)
        self.assertNotContains(response, pending.title)

        detail_response = self.client.get(reverse("reports:report_detail", args=[pending.id]))
        self.assertEqual(detail_response.status_code, 404)


class ContactReporterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.creator = User.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.sender = User.objects.create_user(
            username="sender@eafit.edu.co",
            email="sender@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Documents")

    def create_report(self, status=ItemReport.Status.ACTIVE, creator=None):
        return ItemReport.objects.create(
            title=f"{status} report",
            description="Report description",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=creator or self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=status,
        )

    def test_authenticated_user_can_contact_another_users_active_report(self):
        report = self.create_report()
        self.client.login(username=self.sender.email, password="StrongPass123")

        response = self.client.post(
            reverse("reports:contact_reporter", args=[report.id]),
            {"message": "I think I found this item."},
        )

        self.assertRedirects(
            response,
            reverse("reports:report_detail", args=[report.id]),
        )
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_anonymous_user_cannot_contact_reporter(self):
        report = self.create_report()

        response = self.client.get(
            reverse("reports:contact_reporter", args=[report.id])
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(ContactMessage.objects.exists())

    def test_user_cannot_contact_their_own_report(self):
        report = self.create_report(creator=self.sender)
        self.client.login(username=self.sender.email, password="StrongPass123")

        response = self.client.get(
            reverse("reports:contact_reporter", args=[report.id])
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(ContactMessage.objects.exists())

    def test_user_cannot_contact_pending_review_report(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.client.login(username=self.sender.email, password="StrongPass123")

        response = self.client.get(
            reverse("reports:contact_reporter", args=[report.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_contact_rejected_report(self):
        report = self.create_report(status=ItemReport.Status.REJECTED)
        self.client.login(username=self.sender.email, password="StrongPass123")

        response = self.client.get(
            reverse("reports:contact_reporter", args=[report.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_contact_recovered_report(self):
        report = self.create_report(status=ItemReport.Status.RECOVERED)
        self.client.login(username=self.sender.email, password="StrongPass123")

        response = self.client.get(
            reverse("reports:contact_reporter", args=[report.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_empty_message_is_rejected(self):
        report = self.create_report()
        self.client.login(username=self.sender.email, password="StrongPass123")

        response = self.client.post(
            reverse("reports:contact_reporter", args=[report.id]),
            {"message": "   "},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Message cannot be empty.")
        self.assertFalse(ContactMessage.objects.exists())

    def test_message_is_associated_with_sender_and_report(self):
        report = self.create_report()
        self.client.login(username=self.sender.email, password="StrongPass123")

        self.client.post(
            reverse("reports:contact_reporter", args=[report.id]),
            {"message": "Can we coordinate through BackToYou?"},
        )

        message = ContactMessage.objects.get()
        self.assertEqual(message.sender, self.sender)
        self.assertEqual(message.report, report)
        self.assertEqual(message.report.creator, self.creator)
        self.assertIsNotNone(message.created_at)

    def test_contact_button_visibility_rules(self):
        report = self.create_report()

        anonymous_response = self.client.get(
            reverse("reports:report_detail", args=[report.id])
        )
        self.assertNotContains(anonymous_response, "Contact Reporter")

        self.client.login(username=self.sender.email, password="StrongPass123")
        sender_response = self.client.get(
            reverse("reports:report_detail", args=[report.id])
        )
        self.assertContains(sender_response, "Contact Reporter")
        self.client.logout()

        self.client.login(username=self.creator.email, password="StrongPass123")
        creator_response = self.client.get(
            reverse("reports:report_detail", args=[report.id])
        )
        self.assertNotContains(creator_response, "Contact Reporter")


class ReportModerationTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.regular_user = UserModel.objects.create_user(
            username="regular@eafit.edu.co",
            email="regular@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.REGULAR_USER,
        )
        self.admin_user = UserModel.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.creator = UserModel.objects.create_user(
            username="creator-moderation@eafit.edu.co",
            email="creator-moderation@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Accessories")

    def create_report(self, title, status=ItemReport.Status.PENDING_REVIEW):
        return ItemReport.objects.create(
            title=title,
            description=f"{title} description",
            category=self.category,
            event_date="2026-08-10",
            location="Block 19",
            creator=self.creator,
            report_type=ItemReport.ReportType.FOUND,
            status=status,
        )

    def test_anonymous_user_cannot_access_pending_report_moderation(self):
        response = self.client.get(reverse("administration_pending_reports"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_regular_user_cannot_access_pending_report_moderation(self):
        self.client.login(username=self.regular_user.email, password="StrongPass123")

        response = self.client.get(reverse("administration_pending_reports"))

        self.assertEqual(response.status_code, 403)

    def test_administrator_can_view_pending_reports(self):
        pending = self.create_report("Pending report")
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.get(reverse("administration_pending_reports"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pending.title)

    def test_pending_list_only_contains_pending_review_reports(self):
        pending = self.create_report("Pending visible")
        active = self.create_report("Active hidden", ItemReport.Status.ACTIVE)
        rejected = self.create_report("Rejected hidden", ItemReport.Status.REJECTED)
        recovered = self.create_report("Recovered hidden", ItemReport.Status.RECOVERED)
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.get(reverse("administration_pending_reports"))

        self.assertContains(response, pending.title)
        self.assertNotContains(response, active.title)
        self.assertNotContains(response, rejected.title)
        self.assertNotContains(response, recovered.title)

    def test_administrator_can_review_pending_report(self):
        report = self.create_report("Review me")
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.get(
            reverse("administration_moderate_report", args=[report.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, report.title)
        self.assertContains(response, report.description)
        self.assertContains(response, report.category.name)
        self.assertContains(response, report.get_report_type_display())
        self.assertContains(response, report.location)
        self.assertContains(response, "User #")
        self.assertContains(response, report.get_status_display())

    def test_administrator_can_approve_pending_report(self):
        report = self.create_report("Approve me")
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.post(
            reverse("administration_moderate_report", args=[report.id]),
            {"action": "approve"},
        )

        self.assertRedirects(response, reverse("administration_pending_reports"))
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.ACTIVE)
        self.assertEqual(report.moderated_by, self.admin_user)
        self.assertIsNotNone(report.moderated_at)

    def test_administrator_can_reject_pending_report(self):
        report = self.create_report("Reject me")
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.post(
            reverse("administration_moderate_report", args=[report.id]),
            {"action": "reject"},
        )

        self.assertRedirects(response, reverse("administration_pending_reports"))
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.REJECTED)
        self.assertEqual(report.moderated_by, self.admin_user)
        self.assertIsNotNone(report.moderated_at)

    def test_active_report_cannot_be_moderated_again(self):
        report = self.create_report("Already active", ItemReport.Status.ACTIVE)
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.post(
            reverse("administration_moderate_report", args=[report.id]),
            {"action": "reject"},
        )

        self.assertEqual(response.status_code, 404)
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.ACTIVE)
        self.assertIsNone(report.moderated_by)
        self.assertIsNone(report.moderated_at)

    def test_rejected_report_cannot_be_moderated_again(self):
        report = self.create_report("Already rejected", ItemReport.Status.REJECTED)
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.post(
            reverse("administration_moderate_report", args=[report.id]),
            {"action": "approve"},
        )

        self.assertEqual(response.status_code, 404)

    def test_recovered_report_cannot_be_moderated(self):
        report = self.create_report("Recovered report", ItemReport.Status.RECOVERED)
        self.client.login(username=self.admin_user.email, password="StrongPass123")

        response = self.client.post(
            reverse("administration_moderate_report", args=[report.id]),
            {"action": "approve"},
        )

        self.assertEqual(response.status_code, 404)

    def test_regular_user_cannot_directly_post_approval_or_rejection(self):
        report = self.create_report("Regular blocked")
        self.client.login(username=self.regular_user.email, password="StrongPass123")

        response = self.client.post(
            reverse("administration_moderate_report", args=[report.id]),
            {"action": "approve"},
        )

        self.assertEqual(response.status_code, 403)
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)
        self.assertIsNone(report.moderated_by)
        self.assertIsNone(report.moderated_at)
