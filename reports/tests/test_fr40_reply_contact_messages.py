"""FR40: internal replies, participant privacy and RF08 regression."""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from reports.models import Category, ContactMessage, ItemReport


class ReplyContactMessageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.sender, cls.creator, cls.outsider = [
            User.objects.create_user(username=name, email=f"{name}@eafit.edu.co", password="StrongPass123")
            for name in ("sender", "creator", "outsider")
        ]
        cls.admin = User.objects.create_user(
            username="admin", email="admin@eafit.edu.co", role=User.Role.ADMINISTRATOR,
            is_staff=True, is_superuser=True,
        )
        category = Category.objects.create(name="Electronics")
        cls.report, cls.other_report = [
            ItemReport.objects.create(
                title=title, description="Calculator", category=category,
                event_date="2026-08-10", location="Library", creator=cls.creator,
                report_type=ItemReport.ReportType.LOST, status=ItemReport.Status.ACTIVE,
            ) for title in ("First report", "Other report")
        ]
        cls.original = ContactMessage.objects.create(
            report=cls.report, sender=cls.sender, message="Private original A",
        )

    def detail_url(self, report=None):
        return reverse("reports:report_detail", args=[(report or self.report).pk])

    def reply_url(self, message=None):
        return reverse("reports:reply_to_contact_message", args=[(message or self.original).pk])

    def contact_url(self, report=None):
        return reverse("reports:contact_reporter", args=[(report or self.report).pk])

    def add_reply(self, original=None, text="Private reply B"):
        original = original or self.original
        return ContactMessage.objects.create(
            report=original.report, sender=self.creator, parent_message=original, message=text,
        )

    def test_complete_contact_reply_and_return_flow(self):
        self.client.force_login(self.sender)
        response = self.client.get(self.contact_url())
        self.assertTemplateUsed(response, "reports/contact_reporter.html")
        response = self.client.post(self.contact_url(), {"message": "New contact from A"})
        self.assertRedirects(response, self.detail_url())
        original = ContactMessage.objects.get(message="New contact from A")
        self.assertEqual((original.sender, original.report, original.parent_message),
                         (self.sender, self.report, None))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.creator.email])
        self.client.logout()
        self.client.force_login(self.creator)
        response = self.client.get(self.detail_url())
        self.assertContains(response, self.reply_url(original))
        response = self.client.get(self.reply_url(original))
        self.assertTemplateUsed(response, "reports/reply_contact_message.html")
        self.assertContains(response, original.message)
        response = self.client.post(self.reply_url(original), {"message": "Answer from B"})
        self.assertRedirects(response, self.detail_url())
        reply = original.replies.get()
        self.assertEqual((reply.sender, reply.report, reply.parent_message),
                         (self.creator, self.report, original))
        self.client.logout()
        self.client.force_login(self.sender)
        response = self.client.get(self.detail_url())
        self.assertContains(response, original.message, count=1)
        self.assertContains(response, reply.message, count=1)
        self.assertNotContains(response, self.reply_url(original))
        self.assertNotIn(reply, response.context["contact_messages"])

    def test_non_creators_cannot_get_or_post_reply_even_administrators(self):
        for user in (self.sender, self.outsider, self.admin):
            self.client.force_login(user)
            for method in ("get", "post"):
                with self.subTest(user=user.username, method=method):
                    response = getattr(self.client, method)(self.reply_url(), {"message": "Forbidden"})
                    self.assertEqual(response.status_code, 403)
                    self.assertNotContains(response, self.original.message, status_code=403)
        self.assertFalse(self.original.replies.exists())

    def test_anonymous_contact_and_reply_require_login(self):
        for url in (self.contact_url(), self.reply_url()):
            for method in ("get", "post"):
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url, {"message": "Forbidden"} if method == "post" else {})
                    self.assertRedirects(response, reverse("accounts:login") + "?next=" + url,
                                         fetch_redirect_response=False)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_nonparticipants_and_anonymous_cannot_see_conversations(self):
        reply = self.add_reply()
        for user in (None, self.outsider, self.admin):
            self.client.logout()
            if user:
                self.client.force_login(user)
            with self.subTest(user=user):
                response = self.client.get(self.detail_url())
                self.assertNotContains(response, self.original.message)
                self.assertNotContains(response, reply.message)
                self.assertEqual(list(response.context["contact_messages"]), [])

    def test_participants_only_see_their_own_threads_on_same_report(self):
        other = ContactMessage.objects.create(report=self.report, sender=self.outsider,
                                              message="Private original C")
        reply_a = self.add_reply()
        reply_c = self.add_reply(other, "Private reply to C")
        for user, own, own_reply, hidden, hidden_reply in (
            (self.sender, self.original, reply_a, other, reply_c),
            (self.outsider, other, reply_c, self.original, reply_a),
        ):
            self.client.force_login(user)
            response = self.client.get(self.detail_url())
            self.assertContains(response, own.message)
            self.assertContains(response, own_reply.message)
            self.assertNotContains(response, hidden.message)
            self.assertNotContains(response, hidden_reply.message)
            self.assertEqual(list(response.context["contact_messages"]), [own])
        self.client.force_login(self.creator)
        response = self.client.get(self.detail_url())
        for message in (self.original, other, reply_a, reply_c):
            self.assertContains(response, message.message, count=1)

    def test_reply_ignores_forged_relationships_and_does_not_leak_to_other_report(self):
        other = ContactMessage.objects.create(report=self.other_report, sender=self.outsider, message="Other thread")
        self.client.force_login(self.creator)
        response = self.client.post(self.reply_url(), {
            "message": "Correctly linked", "sender": self.outsider.pk,
            "report": self.other_report.pk, "parent_message": other.pk,
        })
        self.assertRedirects(response, self.detail_url())
        reply = self.original.replies.get()
        self.assertEqual((reply.sender, reply.report, reply.parent_message),
                         (self.creator, self.report, self.original))
        self.assertFalse(other.replies.exists())
        for user in (self.creator, self.sender):
            self.client.force_login(user)
            response = self.client.get(self.detail_url(self.other_report))
            self.assertNotContains(response, reply.message)
            self.assertNotContains(response, self.original.message)

    def test_missing_message_or_reply_as_parent_returns_404(self):
        reply = self.add_reply()
        self.client.force_login(self.creator)
        for pk in (999999, reply.pk):
            for method in ("get", "post"):
                with self.subTest(pk=pk, method=method):
                    response = getattr(self.client, method)(
                        reverse("reports:reply_to_contact_message", args=[pk]), {"message": "Nested"})
                    self.assertEqual(response.status_code, 404)
        self.assertEqual(ContactMessage.objects.count(), 2)

    def test_invalid_reply_has_form_error_and_is_not_saved(self):
        self.client.force_login(self.creator)
        for data in ({}, {"message": "   "}):
            response = self.client.post(self.reply_url(), data)
            self.assertEqual(response.status_code, 200)
            self.assertFormError(response.context["form"], "message", "Message cannot be empty.")
        self.assertFalse(self.original.replies.exists())

    def test_reply_post_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.creator)
        response = client.get(self.reply_url())
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertEqual(client.post(self.reply_url(), {"message": "No token"}).status_code, 403)
        self.assertFalse(self.original.replies.exists())
        response = client.post(self.reply_url(), {
            "message": "Valid token", "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertRedirects(response, self.detail_url())

    def test_contact_form_ignores_forged_parent_sender_and_report(self):
        self.client.force_login(self.sender)
        response = self.client.post(self.contact_url(), {
            "message": "Still a root contact", "parent_message": self.original.pk,
            "sender": self.creator.pk, "report": self.other_report.pk,
        })
        self.assertRedirects(response, self.detail_url())
        contact = ContactMessage.objects.get(message="Still a root contact")
        self.assertEqual((contact.sender, contact.report, contact.parent_message),
                         (self.sender, self.report, None))

    def test_contact_own_report_is_forbidden(self):
        self.client.force_login(self.creator)
        for method in ("get", "post"):
            self.assertEqual(getattr(self.client, method)(self.contact_url(), {"message": "Self"}).status_code, 403)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_contact_nonactive_or_missing_report_returns_404(self):
        self.client.force_login(self.sender)
        for status in (ItemReport.Status.PENDING_REVIEW, ItemReport.Status.REJECTED, ItemReport.Status.RECOVERED):
            self.report.status = status
            self.report.save()
            for method in ("get", "post"):
                with self.subTest(status=status, method=method):
                    self.assertEqual(getattr(self.client, method)(self.contact_url(), {"message": "Hidden"}).status_code, 404)
            self.assertEqual(self.client.get(self.detail_url()).status_code, 404)
        for method in ("get", "post"):
            response = getattr(self.client, method)(reverse("reports:contact_reporter", args=[999999]), {"message": "Missing"})
            self.assertEqual(response.status_code, 404)
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_invalid_contact_does_not_save_or_notify(self):
        self.client.force_login(self.sender)
        response = self.client.post(self.contact_url(), {"message": "   "})
        self.assertFormError(response.context["form"], "message", "Message cannot be empty.")
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_messages_and_replies_are_html_escaped(self):
        self.original.message = '<script>alert("original")</script>'
        self.original.save()
        reply = self.add_reply(text='<script>alert("reply")</script>')
        self.client.force_login(self.sender)
        response = self.client.get(self.detail_url())
        for message in (self.original, reply):
            self.assertNotContains(response, message.message)
        self.assertContains(response, "&lt;script&gt;", count=2)
