"""El creador de un reporte debe poder leer los mensajes que le enviaron.

Completa el ciclo de RF08: el mensaje ya se guardaba asociado al reporte y al
remitente, pero el destinatario no tenia donde verlo.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Category, ContactMessage, ItemReport


class ContactMessagesVisibilityTests(TestCase):
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
        )
        self.message = ContactMessage.objects.create(
            report=self.report,
            sender=self.sender,
            message="I think I found your calculator",
        )
        self.url = reverse("reports:report_detail", args=[self.report.id])

    def login_as(self, user):
        self.client.login(username=user.email, password="StrongPass123")

    def test_creator_sees_the_messages_received(self):
        self.login_as(self.creator)

        response = self.client.get(self.url)

        self.assertContains(response, "Messages about this report")
        self.assertContains(response, "I think I found your calculator")
        self.assertContains(response, self.sender.email)

    def test_another_user_does_not_see_the_messages(self):
        self.login_as(self.sender)

        response = self.client.get(self.url)

        self.assertNotContains(response, "Messages about this report")
        self.assertNotContains(response, "I think I found your calculator")

    def test_anonymous_visitor_does_not_see_the_messages(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "Messages about this report")
        self.assertNotContains(response, "I think I found your calculator")

    def test_creator_without_messages_sees_no_section(self):
        ContactMessage.objects.all().delete()
        self.login_as(self.creator)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Messages about this report")

    def test_messages_are_ordered_from_most_recent_to_oldest(self):
        segundo = ContactMessage.objects.create(
            report=self.report,
            sender=self.sender,
            message="Are you still looking for it?",
        )
        self.login_as(self.creator)

        response = self.client.get(self.url)

        self.assertEqual(
            list(response.context["contact_messages"]),
            [segundo, self.message],
        )
