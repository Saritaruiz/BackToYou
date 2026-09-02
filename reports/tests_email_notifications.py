"""RF15 - Email Notifications."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from .models import Category, ContactMessage, ItemReport


@override_settings(
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend",
        },
    }
)
class EmailNotificationTests(TestCase):
    def setUp(self):
        UserModel = get_user_model()
        self.creator = UserModel.objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.sender = UserModel.objects.create_user(
            username="sender@eafit.edu.co",
            email="sender@eafit.edu.co",
            password="StrongPass123",
        )
        self.admin_user = UserModel.objects.create_user(
            username="admin@eafit.edu.co",
            email="admin@eafit.edu.co",
            password="StrongPass123",
            role=User.Role.ADMINISTRATOR,
        )
        self.category = Category.objects.create(name="Electronics")

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

    def contact_url(self, report):
        return reverse("reports:contact_reporter", args=[report.id])

    def moderation_url(self, report):
        return reverse("administration_moderate_report", args=[report.id])

    def login_as_sender(self):
        self.client.login(username=self.sender.email, password="StrongPass123")

    def login_as_admin(self):
        self.client.login(username=self.admin_user.email, password="StrongPass123")

    def test_valid_contact_message_sends_email_to_report_creator(self):
        report = self.create_report()
        self.login_as_sender()

        response = self.client.post(
            self.contact_url(report),
            {"message": "I think I found this calculator."},
        )

        self.assertRedirects(response, reverse("reports:report_detail", args=[report.id]))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.creator.email])
        self.assertEqual(email.subject, "BackToYou - New message about your report")
        self.assertIn(report.title, email.body)
        self.assertIn("I think I found this calculator.", email.body)
        self.assertIn("Log into BackToYou", email.body)
        self.assertNotIn(self.sender.email, email.body)

    def test_invalid_contact_message_sends_no_email(self):
        report = self.create_report()
        self.login_as_sender()

        response = self.client.post(self.contact_url(report), {"message": "   "})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_contacting_disallowed_report_sends_no_email(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_sender()

        response = self.client.post(self.contact_url(report), {"message": "Hello"})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_contact_message_remains_saved_if_email_sending_fails(self):
        report = self.create_report()
        self.login_as_sender()

        with patch("reports.email_notifications.send_mail", side_effect=Exception("boom")):
            response = self.client.post(
                self.contact_url(report),
                {"message": "I think I found this calculator."},
            )

        self.assertRedirects(response, reverse("reports:report_detail", args=[report.id]))
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(ContactMessage.objects.get().report, report)

    def test_approving_report_sends_email_to_creator(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_admin()

        response = self.client.post(self.moderation_url(report), {"action": "approve"})

        self.assertRedirects(response, reverse("administration_pending_reports"))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.creator.email])
        self.assertEqual(email.subject, "BackToYou - Your report was approved")
        self.assertIn(report.title, email.body)
        self.assertIn("Status: ACTIVE", email.body)
        self.assertIn("publicly visible", email.body)

    def test_invalid_moderation_action_sends_no_email(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_admin()

        response = self.client.post(self.moderation_url(report), {"action": "archive"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.PENDING_REVIEW)

    def test_report_remains_active_if_approved_email_sending_fails(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_admin()

        with patch("reports.email_notifications.send_mail", side_effect=Exception("boom")):
            response = self.client.post(self.moderation_url(report), {"action": "approve"})

        self.assertRedirects(response, reverse("administration_pending_reports"))
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.ACTIVE)
        self.assertEqual(report.moderated_by, self.admin_user)

    def test_rejecting_report_sends_email_to_creator(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_admin()

        response = self.client.post(self.moderation_url(report), {"action": "reject"})

        self.assertRedirects(response, reverse("administration_pending_reports"))
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.creator.email])
        self.assertEqual(email.subject, "BackToYou - Your report was rejected")
        self.assertIn(report.title, email.body)
        self.assertIn("Status: REJECTED", email.body)
        self.assertIn("will not appear in the public report list", email.body)

    def test_report_remains_rejected_if_rejected_email_sending_fails(self):
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_admin()

        with patch("reports.email_notifications.send_mail", side_effect=Exception("boom")):
            response = self.client.post(self.moderation_url(report), {"action": "reject"})

        self.assertRedirects(response, reverse("administration_pending_reports"))
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.REJECTED)
        self.assertEqual(report.moderated_by, self.admin_user)

    def test_blank_recipient_email_does_not_crash_or_send_email(self):
        self.creator.email = ""
        self.creator.save(update_fields=["email"])
        report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.login_as_admin()

        response = self.client.post(self.moderation_url(report), {"action": "approve"})

        self.assertRedirects(response, reverse("administration_pending_reports"))
        report.refresh_from_db()
        self.assertEqual(report.status, ItemReport.Status.ACTIVE)
        self.assertEqual(len(mail.outbox), 0)
