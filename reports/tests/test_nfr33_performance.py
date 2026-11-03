"""NFR33: presupuestos SQL de paginas renderizadas y crecimiento sin N+1.

Las peticiones autenticadas incluyen dos consultas de sesion/usuario.
Los datos y el login se preparan fuera de la medicion.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from ..models import Category, ContactMessage, ItemReport, ModerationLogEntry, ReportFlag, ReportReviewNotification
from ..search import possible_matches
from ..statistics import community_numbers, lost_statistics


class PerformanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="owner")
        cls.sender = User.objects.create_user(username="sender", email="sender@eafit.edu.co")
        cls.admin = User.objects.create_user(username="admin", role="ADMINISTRATOR")
        cls.category = Category.objects.create(name="Electronics")

    def report(self, **changes):
        values = dict(title="Black Canon camera", description="Camera leather strap",
                      location="Library", event_date=date(2026, 8, 10), category=self.category,
                      creator=self.owner, status="ACTIVE", report_type="LOST")
        values.update(changes)
        return ItemReport.objects.create(**values)

    def page_queries(self, name, expected, args=None, data=None):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse(name, args=args), data or {})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(queries), expected, f"Query budget for {name}")
        return response

    def thread(self, report):
        message = ContactMessage.objects.create(report=report, sender=self.sender, message="My camera")
        ContactMessage.objects.create(report=report, sender=self.owner, message="Please check", parent_message=message)
        return message

    def notice(self, report):
        entry = ModerationLogEntry.objects.create(
            action="APPROVED", administrator=self.admin, administrator_email="admin@eafit.edu.co",
            report=report, report_title=report.title,
        )
        return ReportReviewNotification.objects.create(
            recipient=self.owner, report=report, moderation_entry=entry,
            kind="APPROVED", message="Approved camera",
        )

    def test_public_list_and_search_have_two_queries_at_both_sizes(self):
        for amount in (1, 20):
            for _ in range(amount):
                self.report()
            for data in ({}, {"q": "camera"}):
                response = self.page_queries("reports:report_list", 2, data=data)
                self.assertEqual(len(response.context["reports"]), ItemReport.objects.count())

    def test_pending_moderation_has_no_category_n_plus_one(self):
        self.client.force_login(self.admin)
        for amount in (1, 20):
            for _ in range(amount):
                self.report(status="PENDING_REVIEW")
            response = self.page_queries("administration_pending_reports", 3)
            self.assertEqual(len(response.context["reports"]), ItemReport.objects.count())

    def test_moderation_detail_fetches_relations_together(self):
        self.client.force_login(self.admin)
        report = self.report(status="PENDING_REVIEW")
        self.page_queries("administration_moderate_report", 3, args=[report.pk])

    def test_anonymous_detail_has_one_query(self):
        report = self.report()
        self.page_queries("reports:report_detail", 1, args=[report.pk])

    def test_owner_detail_threads_and_matches_do_not_grow_queries(self):
        self.client.force_login(self.owner)
        report = self.report()
        for amount in (1, 20):
            for _ in range(amount):
                self.thread(report)
                self.report(report_type="FOUND", creator=self.sender)
            response = self.page_queries("reports:report_detail", 6, args=[report.pk])
            self.assertContains(response, "Please check", count=ContactMessage.objects.filter(parent_message__isnull=False).count())
            self.assertEqual(len(response.context["possible_matches"]), min(5, ItemReport.objects.filter(report_type="FOUND").count()))

    def test_sender_detail_preserves_isolation_with_constant_queries(self):
        report = self.report()
        self.client.force_login(self.sender)
        for amount in (1, 20):
            for _ in range(amount):
                self.thread(report)
                ContactMessage.objects.create(report=report, sender=self.admin, message="Private message")
            response = self.page_queries("reports:report_detail", 6, args=[report.pk])
            self.assertNotContains(response, "Private message")

    def test_contact_and_reply_avoid_loading_report_creator(self):
        report = self.report()
        message = self.thread(report)
        self.client.force_login(self.sender)
        self.page_queries("reports:contact_reporter", 3, args=[report.pk])
        self.client.force_login(self.owner)
        self.page_queries("reports:reply_to_contact_message", 3, args=[message.pk])

    def test_owner_history_has_constant_queries(self):
        self.client.force_login(self.owner)
        for amount in (1, 20):
            for _ in range(amount):
                self.report()
            self.page_queries("reports:my_reports", 3)

    def test_flags_keep_constant_queries(self):
        self.client.force_login(self.admin)
        for amount in (1, 20):
            for _ in range(amount):
                ReportFlag.objects.create(report=self.report(), flagged_by=self.sender, reason="OTHER")
            self.page_queries("administration_flagged_reports", 4)

    def test_notifications_and_activity_log_are_bounded(self):
        for amount in (1, 25):
            for _ in range(amount):
                self.notice(self.report())
            self.client.force_login(self.owner)
            response = self.page_queries("reports:notifications", 5)
            self.assertLessEqual(len(response.context["page"]), 20)
            self.client.force_login(self.admin)
            self.page_queries("administration_activity_log", 5)

    def test_statistics_use_fixed_aggregate_queries(self):
        for amount in (1, 20):
            for _ in range(amount):
                self.report()
            with self.assertNumQueries(3):
                summary = lost_statistics()["summary"]
            with self.assertNumQueries(1):
                numbers = community_numbers()
            self.assertEqual(summary["active"], ItemReport.objects.count())
            self.assertEqual(numbers["active"], summary["active"])
        self.client.force_login(self.admin)
        self.page_queries("administration_lost_statistics", 5)

    def test_matches_preserve_top_five_with_many_candidates_in_one_query(self):
        source = self.report()
        candidates = [self.report(report_type="FOUND") for _ in range(100)]
        # El mejor candidato se inserta al final: no truncar antes de puntuar.
        ItemReport.objects.filter(pk__in=[item.pk for item in candidates[:-1]]).update(location="Gym")
        with self.assertNumQueries(1):
            matches = possible_matches(source)
            names = [match.category.name for match in matches]
        self.assertEqual(matches, [candidates[-1], *candidates[:4]])
        self.assertEqual(names, ["Electronics"] * 5)

    def test_home_and_administration_overview_have_fixed_queries(self):
        self.report()
        self.page_queries("home", 2)
        self.client.force_login(self.admin)
        self.page_queries("administration", 3)

    def test_account_lists_have_no_related_user_n_plus_one(self):
        self.client.force_login(self.admin)
        for amount in (1, 20):
            for index in range(amount):
                get_user_model().objects.create_user(username=f"user-{amount}-{index}")
            self.page_queries("administration_user_list", 3)
            self.page_queries("administration_administrator_list", 3)
