"""RF44 - Moderation Activity Log. Un test por criterio de aceptacion."""

from datetime import timedelta

from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Category, ItemReport, ModerationLogEntry, ReportFlag
from ..moderation_log import log_action


PASSWORD = "StrongPass123"
Action = ModerationLogEntry.Action


class ModerationLogTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = self.create_user("admin@eafit.edu.co", role=User.Role.ADMINISTRATOR)
        self.second_admin = self.create_user("second.admin@eafit.edu.co", role=User.Role.ADMINISTRATOR)
        self.member = self.create_user("member@eafit.edu.co")
        self.flagger = self.create_user("flagger@eafit.edu.co")
        self.category = Category.objects.create(name="Electronics")
        self.client.login(username=self.admin.email, password=PASSWORD)

    def create_user(self, email, **extra):
        return get_user_model().objects.create_user(
            username=email, email=email, password=PASSWORD, **extra,
        )

    def create_report(self, title="Lost calculator", status=ItemReport.Status.PENDING_REVIEW):
        return ItemReport.objects.create(
            title=title,
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.member,
            report_type=ItemReport.ReportType.LOST,
            status=status,
        )

    def only_entry(self):
        self.assertEqual(ModerationLogEntry.objects.count(), 1)
        return ModerationLogEntry.objects.get()

    def assert_entry(self, entry, action, report_title, details=""):
        self.assertEqual(entry.action, action)
        self.assertEqual(entry.administrator, self.admin)
        self.assertEqual(entry.administrator_email, self.admin.email)
        self.assertEqual(entry.report_title, report_title)
        self.assertEqual(entry.details, details)
        self.assertLess(timezone.now() - entry.created_at, timedelta(minutes=1))


class ModerationActionsAreRecordedTests(ModerationLogTestCase):
    # Given a report, when an Administrator approves, rejects, edits, or
    # removes it, then the system records the action, the Administrator, the
    # date and time, and the report title.
    def test_approving_a_report_is_recorded(self):
        report = self.create_report()

        self.client.post(reverse("administration_moderate_report", args=[report.id]), {"action": "approve"})

        entry = self.only_entry()
        self.assert_entry(entry, Action.APPROVED, "Lost calculator")
        self.assertEqual(entry.report, report)

    def test_rejecting_a_report_is_recorded(self):
        report = self.create_report()

        self.client.post(reverse("administration_moderate_report", args=[report.id]), {"action": "reject"})

        self.assert_entry(self.only_entry(), Action.REJECTED, "Lost calculator")

    def test_editing_a_report_is_recorded_with_the_changed_fields(self):
        report = self.create_report()

        self.client.post(
            reverse("administration_report_edit", args=[report.id]),
            {
                "title": "Lost graphing calculator",
                "description": "Black scientific calculator",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Library, second floor",
            },
        )

        self.assert_entry(
            self.only_entry(), Action.EDITED, "Lost graphing calculator", "Changed: Title, Location",
        )

    def test_saving_without_changes_is_not_recorded(self):
        report = self.create_report()

        self.client.post(
            reverse("administration_report_edit", args=[report.id]),
            {
                "title": report.title,
                "description": report.description,
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": report.location,
            },
        )

        self.assertFalse(ModerationLogEntry.objects.exists())

    def test_removing_a_pending_report_is_recorded(self):
        report = self.create_report()

        self.client.post(reverse("administration_report_delete", args=[report.id]))

        self.assert_entry(self.only_entry(), Action.REMOVED, "Lost calculator")

    # RF43: descartar avisos y retirar un reporte tambien son acciones de
    # moderacion.
    def test_flag_reviews_are_recorded_with_their_reasons(self):
        dismissed = self.create_report("Blue umbrella", ItemReport.Status.ACTIVE)
        removed = self.create_report("Student card", ItemReport.Status.ACTIVE)
        for report in (dismissed, removed):
            ReportFlag.objects.create(report=report, flagged_by=self.flagger, reason=ReportFlag.Reason.PERSONAL_DATA)
        ReportFlag.objects.create(report=removed, flagged_by=self.admin, reason=ReportFlag.Reason.PERSONAL_DATA)

        self.client.post(reverse("administration_flagged_report", args=[dismissed.id]), {"action": "dismiss"})
        self.client.post(reverse("administration_flagged_report_remove", args=[removed.id]))

        entries = {entry.action: entry for entry in ModerationLogEntry.objects.all()}
        self.assert_entry(entries[Action.FLAGS_DISMISSED], Action.FLAGS_DISMISSED, "Blue umbrella", "Personal data")
        self.assert_entry(
            entries[Action.REMOVED_FROM_PUBLIC], Action.REMOVED_FROM_PUBLIC, "Student card", "Personal data ×2",
        )

    def test_failed_or_invalid_actions_are_not_recorded(self):
        report = self.create_report()

        self.client.post(reverse("administration_moderate_report", args=[report.id]), {"action": "publish"})
        self.client.get(reverse("administration_report_delete", args=[report.id]))

        self.assertFalse(ModerationLogEntry.objects.exists())


class ActivityLogPageTests(ModerationLogTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("administration_activity_log")
        self.report = self.create_report()
        self.first = log_action(self.admin, Action.APPROVED, self.report)
        self.second = log_action(self.second_admin, Action.EDITED, self.report)
        self.third = log_action(self.admin, Action.REJECTED, self.report)

    # Given the administration panel, when an Administrator opens the activity
    # log, then the actions are listed from most recent to oldest.
    def test_entries_are_listed_from_most_recent(self):
        response = self.client.get(self.url)

        self.assertEqual(list(response.context["page"].object_list), [self.third, self.second, self.first])
        self.assertContains(response, "second.admin@eafit.edu.co")

    def test_panel_and_menu_link_to_the_activity_log(self):
        response = self.client.get(reverse("administration"))

        self.assertContains(response, f'href="{self.url}"', count=2)

    # Given the activity log, when an Administrator filters by Administrator
    # or by action type, then only the matching entries are shown.
    def test_filter_by_administrator(self):
        response = self.client.get(self.url, {"administrator": self.second_admin.id})

        self.assertEqual(list(response.context["page"].object_list), [self.second])

    def test_filter_by_action(self):
        response = self.client.get(self.url, {"action": Action.APPROVED})

        self.assertEqual(list(response.context["page"].object_list), [self.first])

    def test_filters_combine_and_ignore_invalid_values(self):
        both = self.client.get(self.url, {"administrator": self.admin.id, "action": Action.EDITED})
        invalid = self.client.get(self.url, {"administrator": "abc", "action": "DELETE_ALL"})

        self.assertEqual(list(both.context["page"].object_list), [])
        self.assertContains(both, "No moderation actions match these filters.")
        self.assertEqual(len(invalid.context["page"].object_list), 3)

    # Given a removed report, when the log is consulted, then its entry is
    # still visible with the report title.
    def test_entry_of_a_deleted_report_keeps_its_title(self):
        self.report.delete()

        response = self.client.get(self.url)

        self.assertContains(response, "Lost calculator", count=3)
        self.assertContains(response, "Deleted", count=3)
        self.third.refresh_from_db()
        self.assertIsNone(self.third.report)

    # Given a Regular User, when they try to open the activity log, then the
    # system denies access.
    def test_regular_user_cannot_open_the_activity_log(self):
        self.client.logout()
        self.client.login(username=self.member.email, password=PASSWORD)

        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_visitor_is_sent_to_login(self):
        self.client.logout()

        self.assertRedirects(self.client.get(self.url), f"{reverse('accounts:login')}?next={self.url}")

    def test_long_logs_are_paginated(self):
        for _ in range(50):
            log_action(self.admin, Action.APPROVED, self.report)

        first_page = self.client.get(self.url)
        second_page = self.client.get(self.url, {"page": 2})

        self.assertEqual(len(first_page.context["page"].object_list), 50)
        self.assertEqual(list(second_page.context["page"].object_list), [self.third, self.second, self.first])


class LogEntriesCannotChangeTests(ModerationLogTestCase):
    # Given a log entry, when anyone tries to edit or delete it from the
    # application, then the system does not allow it.
    def test_entry_cannot_be_edited_or_deleted(self):
        entry = log_action(self.admin, Action.APPROVED, self.create_report())

        entry.report_title = "Something else"
        with self.assertRaises(PermissionDenied):
            entry.save()
        with self.assertRaises(PermissionDenied):
            entry.delete()

        entry.refresh_from_db()
        self.assertEqual(entry.report_title, "Lost calculator")

    def test_django_admin_only_lets_administrators_read_the_log(self):
        model_admin = site._registry[ModerationLogEntry]
        request = RequestFactory().get("/admin/")
        request.user = get_user_model().objects.create_superuser(
            username="root@eafit.edu.co", email="root@eafit.edu.co", password=PASSWORD,
        )

        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))
        self.assertTrue(model_admin.has_view_permission(request))
