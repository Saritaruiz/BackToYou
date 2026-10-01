"""Avisos en vez de paginas 403/404 al navegar (backtoyou/middleware.py)."""

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from backtoyou.middleware import NOT_AVAILABLE_MESSAGE, PERMISSION_MESSAGE

from ..models import Category, ItemReport


BROWSER = {"HTTP_ACCEPT": "text/html,application/xhtml+xml,*/*;q=0.8"}


class FriendlyAccessErrorsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner@eafit.edu.co",
            email="owner@eafit.edu.co",
            password="StrongPass123",
        )
        self.visitor = User.objects.create_user(
            username="visitor@eafit.edu.co",
            email="visitor@eafit.edu.co",
            password="StrongPass123",
        )
        category = Category.objects.create(name="Electronics")
        self.hidden_report = ItemReport.objects.create(
            title="Pending calculator",
            description="Black scientific calculator",
            category=category,
            event_date="2026-08-10",
            location="Library",
            creator=self.owner,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.PENDING_REVIEW,
        )
        self.client.login(username=self.visitor.email, password="StrongPass123")

    def messages_for(self, response):
        return [str(message) for message in get_messages(response.wsgi_request)]

    def test_forbidden_page_returns_home_with_permission_message(self):
        response = self.client.get(reverse("administration"), **BROWSER)

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.messages_for(response), [PERMISSION_MESSAGE])

    def test_forbidden_page_returns_to_the_previous_page_of_the_site(self):
        previous = "http://testserver" + reverse("reports:report_list")

        response = self.client.get(reverse("administration"), HTTP_REFERER=previous, **BROWSER)

        self.assertRedirects(response, previous, fetch_redirect_response=False)

    def test_previous_page_on_another_site_is_ignored(self):
        response = self.client.get(
            reverse("administration"),
            HTTP_REFERER="https://evil.example.com/",
            **BROWSER,
        )

        self.assertRedirects(response, reverse("home"))

    def test_previous_page_equal_to_the_failing_page_goes_home_to_avoid_a_loop(self):
        url = reverse("administration")

        response = self.client.get(url, HTTP_REFERER="http://testserver" + url, **BROWSER)

        self.assertRedirects(response, reverse("home"))

    def test_hidden_report_shows_a_neutral_message_that_does_not_reveal_it(self):
        response = self.client.get(
            reverse("reports:report_detail", args=[self.hidden_report.id]),
            **BROWSER,
        )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.messages_for(response), [NOT_AVAILABLE_MESSAGE])
        self.assertNotIn("permission", NOT_AVAILABLE_MESSAGE.lower())

    def test_address_that_does_not_exist_shows_the_neutral_message(self):
        response = self.client.get("/this-page-does-not-exist/", **BROWSER)

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.messages_for(response), [NOT_AVAILABLE_MESSAGE])

    def test_missing_images_keep_their_404_status(self):
        response = self.client.get("/media/reports/missing.jpg", HTTP_ACCEPT="image/avif,image/webp,*/*")

        self.assertEqual(response.status_code, 404)

    def test_message_is_shown_on_the_page_after_the_redirect(self):
        response = self.client.get(reverse("administration"), follow=True, **BROWSER)

        self.assertContains(response, "You don&#x27;t have permission to access that page.")

    def test_requests_that_are_not_page_navigation_keep_the_403_status(self):
        response = self.client.get(reverse("administration"), HTTP_ACCEPT="application/json")

        self.assertEqual(response.status_code, 403)

    def test_hidden_report_keeps_the_404_status_outside_page_navigation(self):
        response = self.client.get(reverse("reports:report_detail", args=[self.hidden_report.id]))

        self.assertEqual(response.status_code, 404)
