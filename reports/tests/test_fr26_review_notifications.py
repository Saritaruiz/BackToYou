"""FR26: decisiones, lectura privada y atomicidad de las notificaciones."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Category, ItemReport, ModerationLogEntry, ReportReviewNotification


class ReviewNotificationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", email="owner@eafit.edu.co")
        self.other = User.objects.create_user(username="other", email="other@eafit.edu.co")
        self.admin = User.objects.create_user(username="admin", role="ADMINISTRATOR")
        self.category = Category.objects.create(name="Electronics")
        self.report = ItemReport.objects.create(
            title="Canon camera", description="Black camera", category=self.category,
            creator=self.owner, report_type="LOST", event_date="2026-08-10", location="Library",
        )
        self.url = reverse("administration_moderate_report", args=[self.report.pk])
        self.inbox = reverse("reports:notifications")
        self.client.force_login(self.admin)

    def review(self, action="approve"):
        return self.client.post(self.url, {"action": action, "reason": "duplicate"})

    def notice(self):
        return ReportReviewNotification.objects.get()

    def read_url(self, notice=None):
        return reverse("reports:mark_notification_read", args=[(notice or self.notice()).pk])

    def test_approval_creates_unread_notice_for_creator_with_report_and_log(self):
        self.assertEqual(self.review().status_code, 302)
        notice = self.notice()
        self.assertEqual(notice.recipient, self.owner)
        self.assertEqual(notice.report, self.report)
        self.assertEqual(notice.kind, "APPROVED")
        self.assertIn(self.report.title, notice.message)
        self.assertIn("approved", notice.message)
        self.assertEqual(notice.moderation_entry.action, "APPROVED")
        self.assertIsNone(notice.read_at)
        self.assertLess((timezone.now() - notice.created_at).total_seconds(), 5)

    def test_rejection_includes_reason_and_preserves_expiration(self):
        expiry = self.report.expires_at
        self.assertEqual(self.review("reject").status_code, 302)
        notice = self.notice()
        self.report.refresh_from_db()
        self.assertEqual(notice.kind, "REJECTED")
        self.assertIn(self.report.rejection_reason, notice.message)
        self.assertIn(self.report.title, notice.message)
        self.assertEqual(self.report.expires_at, expiry)

    def test_invalid_rejection_and_get_do_not_notify(self):
        self.client.get(self.url)
        response = self.client.post(self.url, {"action": "reject"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ReportReviewNotification.objects.exists())
        self.assertFalse(ModerationLogEntry.objects.exists())

    def test_unauthorized_user_cannot_review_or_notify(self):
        self.client.force_login(self.other)
        self.assertEqual(self.review().status_code, 403)
        self.assertFalse(ReportReviewNotification.objects.exists())

    def test_repeated_decision_does_not_duplicate(self):
        self.review()
        self.assertEqual(self.review().status_code, 404)
        self.assertEqual(ReportReviewNotification.objects.count(), 1)
        self.assertEqual(ModerationLogEntry.objects.count(), 1)

    def test_stale_loaded_report_cannot_duplicate_or_reverse_decision(self):
        stale = ItemReport.objects.get(pk=self.report.pk)
        self.review()
        # Simula una segunda peticion que cargo PENDING antes del primer commit.
        with patch("reports.views.moderation.get_object_or_404", return_value=stale):
            self.assertEqual(self.review("reject").status_code, 404)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "ACTIVE")
        self.assertEqual(ReportReviewNotification.objects.count(), 1)
        self.assertEqual(ModerationLogEntry.objects.count(), 1)

    def test_database_allows_only_one_notification_per_log_entry(self):
        self.review()
        notice = self.notice()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReportReviewNotification.objects.create(
                recipient=self.owner, report=self.report,
                moderation_entry=notice.moderation_entry, kind="APPROVED", message="Duplicate",
            )

    def test_new_review_after_resubmission_produces_a_new_notice(self):
        self.review("reject")
        self.client.force_login(self.owner)
        response = self.client.post(reverse("reports:edit_report", args=[self.report.pk]), {
            "title": self.report.title, "description": "Corrected camera description",
            "category": self.category.pk, "event_date": "2026-08-10", "location": "Library",
        })
        self.assertEqual(response.status_code, 302)
        self.client.force_login(self.admin)
        self.review()
        self.assertEqual(list(ReportReviewNotification.objects.values_list("kind", flat=True)), ["APPROVED", "REJECTED"])

    def test_notification_failure_rolls_back_report_and_history(self):
        with patch("reports.views.moderation.ReportReviewNotification.objects.create", side_effect=RuntimeError("unavailable")):
            with self.assertRaises(RuntimeError):
                self.review()
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, "PENDING_REVIEW")
        self.assertIsNone(self.report.moderated_at)
        self.assertFalse(ModerationLogEntry.objects.exists())
        self.assertFalse(ReportReviewNotification.objects.exists())

    def test_email_failure_does_not_lose_in_app_notification(self):
        with patch("reports.email_notifications.send_mail", side_effect=RuntimeError("offline")):
            with self.assertLogs("reports.email_notifications", level="ERROR"):
                self.assertEqual(self.review().status_code, 302)
        self.assertEqual(self.notice().kind, "APPROVED")

    def test_recipient_sees_message_link_unread_state_without_implicit_read(self):
        self.review()
        self.client.force_login(self.owner)
        response = self.client.get(self.inbox)
        self.assertContains(response, self.report.title)
        self.assertContains(response, "Unread")
        self.assertContains(response, reverse("reports:report_detail", args=[self.report.pk]))
        self.assertEqual(response.context["unread_count"], 1)
        self.assertIsNone(self.notice().read_at)

    def test_other_users_including_admin_cannot_list_or_mark_notice(self):
        self.review()
        url = self.read_url()
        for user in (self.other, self.admin):
            self.client.force_login(user)
            response = self.client.get(self.inbox, {"recipient": self.owner.pk})
            self.assertNotContains(response, self.report.title)
            self.assertEqual(response.context["unread_count"], 0)
            self.assertEqual(self.client.post(url).status_code, 404)
        self.assertIsNone(self.notice().read_at)

    def test_owner_marks_read_and_repeated_post_preserves_first_read_date(self):
        self.review()
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.post(self.read_url()), self.inbox)
        read_at = self.notice().read_at
        self.assertIsNotNone(read_at)
        self.client.post(self.read_url())
        self.assertEqual(self.notice().read_at, read_at)
        response = self.client.get(self.inbox)
        self.assertEqual(response.context["unread_count"], 0)
        self.assertNotContains(response, "Mark as read")

    def test_read_requires_post_and_csrf(self):
        self.review()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.read_url()).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.read_url()).status_code, 403)
        self.assertIsNone(self.notice().read_at)

    def test_login_required_and_navigation_is_authenticated_only(self):
        self.review()
        self.client.logout()
        self.assertEqual(self.client.get(self.inbox).status_code, 302)
        self.assertEqual(self.client.post(self.read_url()).status_code, 302)
        self.assertNotContains(self.client.get(reverse("reports:report_list")), self.inbox)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("reports:my_reports")), self.inbox)

    def test_snapshot_survives_report_changes_and_deletion(self):
        self.review()
        message = self.notice().message
        self.report.title = "Changed title"
        self.report.save(update_fields=["title"])
        self.report.delete()
        self.assertEqual(self.notice().message, message)
        self.assertIsNone(self.notice().report_id)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(self.inbox), "This report has been deleted.")

    def test_notification_message_is_escaped(self):
        self.report.title = "<script>alert(1)</script>"
        self.report.save(update_fields=["title"])
        self.review()
        self.client.force_login(self.owner)
        response = self.client.get(self.inbox)
        self.assertNotContains(response, self.report.title)
        self.assertContains(response, "&lt;script&gt;")

    def test_pagination_is_stable_and_scoped_to_recipient(self):
        now = timezone.now()
        notices = []
        for _ in range(22):
            entry = ModerationLogEntry.objects.create(
                action="APPROVED", administrator=self.admin, administrator_email="admin@eafit.edu.co",
                report=self.report, report_title=self.report.title,
            )
            notices.append(ReportReviewNotification.objects.create(
                recipient=self.owner, report=self.report, moderation_entry=entry,
                kind="APPROVED", message="Reviewed",
            ))
        ReportReviewNotification.objects.update(created_at=now)
        self.client.force_login(self.owner)
        response = self.client.get(self.inbox)
        self.assertEqual(list(response.context["page"]), list(reversed(notices))[:20])
        response = self.client.get(self.inbox, {"page": 2})
        self.assertEqual(list(response.context["page"]), list(reversed(notices))[20:])
        self.assertEqual(response.context["unread_count"], 22)
