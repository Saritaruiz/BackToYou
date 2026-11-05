"""FR41: sugerencias deterministas y privacidad del detalle."""

from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Category, ContactMessage, ItemReport
from ..search import possible_matches


class MatchSuggestionsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            username="owner", email="owner@eafit.edu.co", password="StrongPass123",
        )
        cls.other = User.objects.create_user(
            username="other", email="other@eafit.edu.co", password="StrongPass123",
        )
        cls.category = Category.objects.create(name="Electronics")

    def make_report(self, **changes):
        values = dict(
            title="Lost black Canon camera",
            description="Canon camera with leather strap",
            category=self.category,
            event_date=date(2026, 8, 10),
            location="Library second floor",
            creator=self.other,
            report_type=ItemReport.ReportType.FOUND,
            status=ItemReport.Status.ACTIVE,
        )
        values.update(changes)
        return ItemReport.objects.create(**values)

    def setUp(self):
        self.report = self.make_report(
            creator=self.owner, report_type=ItemReport.ReportType.LOST,
        )
        self.url = reverse("reports:report_detail", args=[self.report.pk])

    def test_lost_finds_found(self):
        candidate = self.make_report()
        self.assertEqual(possible_matches(self.report), [candidate])

    def test_found_finds_lost(self):
        candidate = self.make_report()
        self.assertEqual(possible_matches(candidate), [self.report])

    def test_different_categories_are_excluded(self):
        category = Category.objects.create(name="Keys")
        self.make_report(category=category)
        self.assertEqual(possible_matches(self.report), [])

    def test_nonpublic_candidates_are_excluded_even_when_owned(self):
        for status in ItemReport.Status.values:
            if status != ItemReport.Status.ACTIVE:
                with self.subTest(status=status):
                    self.make_report(status=status, creator=self.owner)
        self.assertEqual(possible_matches(self.report), [])

    def test_self_and_same_type_are_excluded(self):
        self.make_report(report_type=ItemReport.ReportType.LOST)
        self.assertEqual(possible_matches(self.report), [])

    def test_location_and_date_alone_do_not_make_a_match(self):
        self.make_report(title="Found headphones", description="Wireless headphones")
        self.assertEqual(possible_matches(self.report), [])

    def test_one_generic_shared_word_is_not_enough(self):
        self.make_report(title="Black headphones", description="Wireless headphones")
        self.assertEqual(possible_matches(self.report), [])

    def test_stop_words_alone_do_not_make_a_match(self):
        self.report.title = "Lost item"
        self.report.description = "The item was lost in the library"
        self.make_report(title="Found item", description="The item was found")
        self.assertEqual(possible_matches(self.report), [])

    def test_accents_case_and_punctuation_are_normalized(self):
        self.report.title = "C?mara CANON"
        self.report.description = "Correa de cuero"
        candidate = self.make_report(title="CAMARA, canon!", description="correa cuero")
        self.assertEqual(possible_matches(self.report), [candidate])

    def test_description_can_match_when_titles_differ(self):
        candidate = self.make_report(title="Found photography equipment")
        self.assertEqual(possible_matches(self.report), [candidate])

    def test_matching_single_word_titles_are_useful(self):
        self.report.title = "Calculator"
        self.report.description = ""
        candidate = self.make_report(title="Found calculator", description="")
        self.assertEqual(possible_matches(self.report), [candidate])

    def test_stronger_text_ranks_above_weaker_text(self):
        weaker = self.make_report(title="Canon camera", description="Digital camera")
        stronger = self.make_report()
        self.assertEqual(possible_matches(self.report), [stronger, weaker])

    def test_location_and_date_prioritize_otherwise_identical_matches(self):
        elsewhere = self.make_report(location="Sports field")
        older = self.make_report(event_date=self.report.event_date - timedelta(days=60))
        nearby = self.make_report(event_date=self.report.event_date + timedelta(days=1))
        exact = self.make_report()
        self.assertEqual(possible_matches(self.report), [exact, nearby, older, elsewhere])

    def test_limit_and_tie_break_are_deterministic(self):
        candidates = [self.make_report() for _ in range(7)]
        self.assertEqual(possible_matches(self.report), candidates[:5])
        self.assertEqual(possible_matches(self.report), candidates[:5])

    def test_candidates_and_categories_use_one_query(self):
        for _ in range(7):
            self.make_report()
        with self.assertNumQueries(1):
            matches = possible_matches(self.report)
            self.assertEqual([item.category.name for item in matches], ["Electronics"] * 5)

    def test_owner_sees_links_without_candidate_private_information(self):
        candidate = self.make_report(rejection_reason="Private moderation note")
        ContactMessage.objects.create(
            report=candidate, sender=self.owner, message="Private candidate message",
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, "Possible matches")
        self.assertEqual(response.context["possible_matches"], [candidate])
        self.assertContains(response, reverse("reports:report_detail", args=[candidate.pk]))
        for private in (self.other.email, "Private moderation note", "Private candidate message"):
            self.assertNotContains(response, private)

    def test_owner_sees_empty_state(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, "No similar active reports found yet.")

    def test_visitors_do_not_compute_or_see_suggestions(self):
        self.make_report()
        for user in (None, self.other):
            with self.subTest(user=user):
                if user:
                    self.client.force_login(user)
                with patch("reports.views.public.possible_matches") as match:
                    response = self.client.get(self.url)
                match.assert_not_called()
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "Possible matches")
                self.assertEqual(response.context["possible_matches"], [])

    def test_unpublished_source_remains_private_and_owner_can_get_matches(self):
        candidate = self.make_report()
        for status in ("PENDING_REVIEW", "REJECTED", "RECOVERED"):
            with self.subTest(status=status):
                self.report.status = status
                self.report.save()
                self.client.logout()
                self.assertEqual(self.client.get(self.url).status_code, 404)
                self.client.force_login(self.other)
                self.assertEqual(self.client.get(self.url).status_code, 404)
                self.client.force_login(self.owner)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["possible_matches"], [candidate])
