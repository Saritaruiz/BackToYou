"""FR45: vigencia, renovacion, privacidad y conservacion del historial."""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

from ..models import Category, ContactMessage, ItemReport, REPORT_VALIDITY, ReportFlag
from ..querysets import public_reports, flagged_reports
from ..search import possible_matches
from ..statistics import community_numbers, lost_statistics


class ExpirationRenewalTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner")
        self.other = User.objects.create_user(username="other")
        self.admin = User.objects.create_user(username="admin", role="ADMINISTRATOR")
        self.category = Category.objects.create(name="Electronics")
        self.report = ItemReport.objects.create(
            title="Black Canon camera", description="Camera with leather strap",
            category=self.category, creator=self.owner, report_type="LOST",
            status="ACTIVE", event_date=date(2026, 8, 10), location="Library",
        )
        self.detail = reverse("reports:report_detail", args=[self.report.pk])
        self.renew = reverse("reports:renew_report", args=[self.report.pk])

    def expire(self):
        self.report.expires_at = timezone.now() - timedelta(days=1)
        self.report.save(update_fields=["expires_at"])

    def test_default_validity_is_thirty_days(self):
        self.assertAlmostEqual(
            (self.report.expires_at - self.report.created_at).total_seconds(),
            REPORT_VALIDITY.total_seconds(), delta=1,
        )
        self.assertFalse(self.report.is_expired)
        self.assertTrue(self.report.is_public)

    def test_expiration_boundary_agrees_with_public_queryset(self):
        boundary = self.report.expires_at
        for offset, expired in ((-1, False), (0, True), (1, True)):
            with self.subTest(offset=offset), patch(
                "django.utils.timezone.now", return_value=boundary + timedelta(microseconds=offset),
            ):
                self.assertEqual(self.report.is_expired, expired)
                self.assertEqual(public_reports().filter(pk=self.report.pk).exists(), not expired)

    def test_nonactive_states_are_not_expired_public_or_renewable(self):
        self.expire()
        self.client.force_login(self.owner)
        for status in ("PENDING_REVIEW", "REJECTED", "RECOVERED"):
            with self.subTest(status=status):
                self.report.status = status
                self.report.save(update_fields=["status"])
                self.assertFalse(self.report.is_expired)
                self.assertFalse(self.report.is_public)
                self.assertFalse(self.report.can_be_renewed)
                self.assertEqual(self.client.get(self.renew).status_code, 403)
                self.assertEqual(self.client.post(self.renew).status_code, 403)
                self.report.refresh_from_db()
                self.assertEqual(self.report.status, status)

    def test_expired_report_is_excluded_from_list_and_search(self):
        self.expire()
        for query in ({}, {"q": "Canon"}):
            response = self.client.get(reverse("reports:report_list"), query)
            self.assertEqual(list(response.context["reports"]), [])

    def test_expired_candidate_is_excluded_from_matches(self):
        self.expire()
        source = ItemReport.objects.create(
            title=self.report.title, description=self.report.description,
            category=self.category, creator=self.other, report_type="FOUND",
            status="ACTIVE", event_date=self.report.event_date, location="Library",
        )
        self.assertEqual(possible_matches(source), [])

    def test_expired_detail_is_private_but_owner_sees_expiration_and_renewal(self):
        self.expire()
        self.assertEqual(self.client.get(self.detail).status_code, 404)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(self.detail).status_code, 404)
        self.client.force_login(self.owner)
        response = self.client.get(self.detail)
        self.assertContains(response, "Expired")
        self.assertContains(response, self.renew)
        history = self.client.get(reverse("reports:my_reports"))
        self.assertContains(history, "Expired")
        self.assertContains(history, self.detail)

    def test_expired_report_cannot_receive_new_contact_or_flags(self):
        self.expire()
        self.client.force_login(self.other)
        for name in ("contact_reporter", "flag_report"):
            url = reverse("reports:" + name, args=[self.report.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {"message": "Hello", "reason": "OTHER"}).status_code, 404)
        self.assertFalse(ContactMessage.objects.exists())
        self.assertFalse(ReportFlag.objects.exists())

    def test_expiration_does_not_hide_pending_flags_from_moderation(self):
        ReportFlag.objects.create(report=self.report, flagged_by=self.other, reason="OTHER")
        self.expire()
        self.assertEqual(list(flagged_reports()), [self.report])

    def test_expired_owner_can_renew_for_thirty_days_from_now(self):
        self.expire()
        self.client.force_login(self.owner)
        now = timezone.now()
        with patch("django.utils.timezone.now", return_value=now):
            response = self.client.post(self.renew)
        self.assertRedirects(response, self.detail)
        self.report.refresh_from_db()
        self.assertEqual(self.report.expires_at, now + REPORT_VALIDITY)
        self.assertFalse(self.report.is_expired)
        self.assertTrue(public_reports().filter(pk=self.report.pk).exists())
        self.client.logout()
        self.assertEqual(self.client.get(self.detail).status_code, 200)

    def test_renewing_before_expiry_extends_remaining_validity(self):
        before = self.report.expires_at
        self.client.force_login(self.owner)
        self.client.post(self.renew)
        self.report.refresh_from_db()
        self.assertEqual(self.report.expires_at, before + REPORT_VALIDITY)

    def test_get_confirmation_does_not_renew(self):
        self.client.force_login(self.owner)
        before = self.report.expires_at
        response = self.client.get(self.renew)
        self.assertContains(response, "Renew this report?")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.report.refresh_from_db()
        self.assertEqual(self.report.expires_at, before)

    def test_renewal_requires_owner_and_login(self):
        before = self.report.expires_at
        self.assertEqual(self.client.post(self.renew).status_code, 302)
        for user in (self.other, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.renew).status_code, 403)
            self.assertEqual(self.client.post(self.renew).status_code, 403)
        self.report.refresh_from_db()
        self.assertEqual(self.report.expires_at, before)

    def test_renewal_requires_csrf_and_supported_method(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.renew).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.put(self.renew).status_code, 405)

    def test_renewal_preserves_history_content_and_messages(self):
        self.expire()
        message = ContactMessage.objects.create(report=self.report, sender=self.other, message="Hello")
        before = ItemReport.objects.values().get(pk=self.report.pk)
        self.client.force_login(self.owner)
        self.client.post(self.renew)
        after = ItemReport.objects.values().get(pk=self.report.pk)
        for field in before.keys() - {"expires_at", "updated_at"}:
            self.assertEqual(before[field], after[field], field)
        self.assertTrue(ContactMessage.objects.filter(pk=message.pk).exists())

    def test_ordinary_edit_does_not_renew(self):
        self.expire()
        before = self.report.expires_at
        self.client.force_login(self.owner)
        response = self.client.post(reverse("reports:edit_report", args=[self.report.pk]), {
            "title": "Edited Canon camera", "description": self.report.description,
            "category": self.category.pk, "event_date": "2026-08-10", "location": "Library",
        })
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.expires_at, before)
        self.assertTrue(self.report.is_expired)

    @patch("reports.views.moderation.notify_report_approved")
    def test_approval_starts_full_validity_after_long_review(self, notify):
        self.expire()
        self.report.status = "PENDING_REVIEW"
        self.report.save(update_fields=["status"])
        self.client.force_login(self.admin)
        now = timezone.now()
        with patch("django.utils.timezone.now", return_value=now):
            response = self.client.post(reverse("administration_moderate_report", args=[self.report.pk]), {"action": "approve"})
        self.assertEqual(response.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.expires_at, now + REPORT_VALIDITY)
        self.assertTrue(self.report.is_public)

    def test_expired_reports_remain_in_statistics_but_not_active_counts(self):
        self.expire()
        summary = lost_statistics()["summary"]
        self.assertEqual((summary["total"], summary["active"], summary["expired"]), (1, 0, 1))
        self.assertEqual(summary["recovery_rate"], 0.0)
        numbers = community_numbers()
        self.assertEqual(numbers["active"], 0)
        self.assertEqual(numbers["new_last_day"], 0)
        self.assertEqual(numbers["recovery_rate"], 0.0)


class ExpirationMigrationTests(TransactionTestCase):
    def test_existing_reports_use_approval_or_creation_without_losing_history(self):
        previous = [("reports", "0008_contactmessage_parent_message")]
        target = [("reports", "0009_itemreport_expires_at")]
        executor = MigrationExecutor(connection)
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            User = apps.get_model("accounts", "User")
            CategoryModel = apps.get_model("reports", "Category")
            Report = apps.get_model("reports", "ItemReport")
            owner = User.objects.create(username="migration-owner")
            category = CategoryModel.objects.create(name="Migration category")
            now = timezone.now()
            created = now - timedelta(days=90)
            approved = now - timedelta(days=10)
            ids = []
            for moderated in (None, approved):
                report = Report.objects.create(
                    title="Historical camera", description="Keep history", creator=owner,
                    category=category, event_date=date(2026, 8, 10), location="Library",
                    status="ACTIVE", report_type="LOST", moderated_at=moderated,
                )
                Report.objects.filter(pk=report.pk).update(created_at=created)
                ids.append(report.pk)
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            old, recent = [ItemReport.objects.get(pk=pk) for pk in ids]
            self.assertEqual(old.expires_at, created + REPORT_VALIDITY)
            self.assertTrue(old.is_expired)
            self.assertEqual(recent.expires_at, approved + REPORT_VALIDITY)
            self.assertFalse(recent.is_expired)
            for report in (old, recent):
                self.assertEqual(report.created_at, created)
                self.assertEqual(report.description, "Keep history")
                self.assertEqual(report.status, "ACTIVE")
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
