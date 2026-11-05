"""FR42: filtros por lugar y fechas, y orden de la lista de reportes."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Category, ItemReport


UMBRELLA, BOTTLE, KEYS = "Black umbrella", "Green bottle", "Silver keys"


class AdvancedSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username="owner@eafit.edu.co", email="owner@eafit.edu.co")
        cls.bags = Category.objects.create(name="Bags")
        cls.bottles = Category.objects.create(name="Bottles")
        # El orden de creacion es distinto del orden de las fechas del evento y
        # del alfabetico, para que cada opcion de orden se distinga de las demas.
        now = timezone.now()
        for title, age, report_type, category, event_date, location in (
            (BOTTLE, 2, "FOUND", cls.bottles, "2026-03-20", "Bloque 38"),
            (UMBRELLA, 1, "LOST", cls.bags, "2026-03-10", "Biblioteca Central"),
            (KEYS, 3, "LOST", cls.bags, "2026-04-05", "Cafetería"),
        ):
            report = cls.report(title, report_type=report_type, category=category, event_date=event_date, location=location)
            ItemReport.objects.filter(pk=report.pk).update(created_at=now - timedelta(days=age))

    @classmethod
    def report(cls, title, **changes):
        data = {
            "title": title,
            "description": "Lost and found item",
            "category": cls.bags,
            "creator": cls.owner,
            "report_type": "LOST",
            "status": "ACTIVE",
            "event_date": "2026-03-15",
            "location": "Library",
        }
        data.update(changes)
        return ItemReport.objects.create(**data)

    def get(self, **params):
        return self.client.get(reverse("reports:report_list"), params)

    def titles(self, **params):
        response = self.get(**params)
        self.assertEqual(response.status_code, 200)
        return [report.title for report in response.context["reports"]]

    def test_date_range_includes_both_limits(self):
        self.assertCountEqual(self.titles(date_from="2026-03-10", date_to="2026-03-20"), [UMBRELLA, BOTTLE])

    def test_one_date_limits_only_that_side(self):
        self.assertCountEqual(self.titles(date_from="2026-03-20"), [BOTTLE, KEYS])
        self.assertCountEqual(self.titles(date_to="2026-03-20"), [UMBRELLA, BOTTLE])

    def test_location_ignores_case_and_accents(self):
        self.assertEqual(self.titles(location="BLOQUE"), [BOTTLE])
        self.assertEqual(self.titles(location="cafeteria"), [KEYS])
        self.assertEqual(self.titles(location="Library"), [])

    def test_each_sort_option_uses_its_own_order(self):
        for sort, expected in {
            "newest": [UMBRELLA, BOTTLE, KEYS],
            "oldest": [KEYS, BOTTLE, UMBRELLA],
            "event_newest": [KEYS, BOTTLE, UMBRELLA],
            "event_oldest": [UMBRELLA, BOTTLE, KEYS],
            "title_asc": [UMBRELLA, BOTTLE, KEYS],
            "title_desc": [KEYS, BOTTLE, UMBRELLA],
        }.items():
            with self.subTest(sort=sort):
                self.assertEqual(self.titles(sort=sort), expected)

    def test_without_a_valid_order_the_newest_come_first(self):
        expected = [UMBRELLA, BOTTLE, KEYS]
        self.assertEqual(self.titles(), expected)
        self.assertEqual(self.titles(sort="nope"), expected)

    def test_filters_combine_with_search_category_and_type(self):
        self.report("Blue umbrella", category=self.bags, event_date="2026-01-01")
        self.report("Found umbrella", report_type="FOUND", event_date="2026-03-12", location="Biblioteca")

        titles = self.titles(
            q="umbrella",
            category=self.bags.id,
            type="LOST",
            location="biblioteca",
            date_from="2026-03-01",
            date_to="2026-03-31",
        )

        self.assertEqual(titles, [UMBRELLA])

    def test_reversed_dates_show_the_empty_state(self):
        response = self.get(date_from="2026-04-01", date_to="2026-03-01")

        self.assertEqual(list(response.context["reports"]), [])
        self.assertContains(response, "No active reports are currently available.")

    def test_selected_values_stay_in_the_form(self):
        response = self.get(location="Bloque", date_from="2026-03-01", date_to="2026-03-31", sort="title_desc")

        self.assertContains(response, 'value="Bloque"')
        self.assertContains(response, 'value="2026-03-01"')
        self.assertContains(response, 'value="2026-03-31"')
        self.assertEqual(response.context["selected_sort"], "title_desc")

    def test_changing_the_view_keeps_the_filters(self):
        response = self.get(location="Bloque", sort="title_asc")

        self.assertContains(response, "?location=Bloque&amp;sort=title_asc&amp;view=list")

    def test_clear_filters_goes_back_to_the_full_list(self):
        response = self.get(location="Bloque")

        self.assertContains(response, f'href="{reverse("reports:report_list")}"')
        self.assertEqual(len(self.titles()), 3)

    def test_filters_never_reveal_reports_that_are_not_public(self):
        self.report("Hidden pending", status="PENDING_REVIEW", location="Bloque 38")
        self.report("Hidden recovered", status="RECOVERED", location="Bloque 38")
        self.report("Hidden expired", location="Bloque 38", expires_at=timezone.now() - timedelta(days=1))

        self.assertEqual(self.titles(location="Bloque 38"), [BOTTLE])

    def test_invalid_dates_are_ignored(self):
        for value in ("abc", "2026-13-45", "2026-02-30", "'; DROP TABLE"):
            with self.subTest(value=value):
                self.assertEqual(len(self.titles(date_from=value)), 3)
                self.assertEqual(len(self.titles(date_to=value)), 3)
                self.assertNotContains(self.get(date_from=value), f'value="{value}"')

    def test_a_valid_date_still_applies_next_to_an_invalid_one(self):
        self.assertCountEqual(self.titles(date_from="abc", date_to="2026-03-20"), [UMBRELLA, BOTTLE])

    def test_an_invalid_category_is_ignored(self):
        for value in ("abc", "999999", "99999999999999999999999", "1 OR 1=1"):
            with self.subTest(value=value):
                response = self.get(category=value)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.context["reports"]), 3)
                self.assertEqual(response.context["selected_category"], "")

    def test_a_valid_category_still_filters(self):
        response = self.get(category=self.bottles.id)

        self.assertEqual([report.title for report in response.context["reports"]], [BOTTLE])
        self.assertEqual(response.context["selected_category"], str(self.bottles.id))
