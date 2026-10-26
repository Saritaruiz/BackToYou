"""RF39 - Password Recovery and Change. Un test por criterio de aceptacion."""

import re
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail
from django.test import TestCase
from django.urls import reverse


PASSWORD = "StrongPass123"
NEW_PASSWORD = "Another-Secret-2026"


class PasswordRecoveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student@eafit.edu.co",
            email="student@eafit.edu.co",
            password=PASSWORD,
        )

    def request_reset(self, email):
        return self.client.post(reverse("accounts:password_reset"), {"email": email}, follow=True)

    def reset_link(self):
        return re.search(r"https?://[^/\s]+(/accounts/reset/\S+/)", mail.outbox[-1].body).group(1)

    def can_login(self, password):
        return self.client.login(username=self.user.username, password=password)

    # Given the login page, when the user selects "Forgot your password?",
    # then the system offers the recovery form.
    def test_login_page_links_to_password_recovery(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, reverse("accounts:password_reset"))
        self.assertContains(response, "Forgot your password?")

    # Given a registered institutional email, when it is entered in the
    # recovery form, then the system sends an email with a link to set a new
    # password.
    def test_registered_email_receives_a_reset_link(self):
        response = self.request_reset("Student@EAFIT.edu.co")

        self.assertContains(response, "Check your inbox.")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["student@eafit.edu.co"])
        self.assertEqual(mail.outbox[0].subject, "BackToYou - Reset your password")
        self.assertIn("/accounts/reset/", mail.outbox[0].body)

    # Given an email that is not registered, when it is entered in the
    # recovery form, then the system shows the same confirmation message,
    # without revealing whether the account exists.
    def test_unregistered_email_gets_the_same_message_and_no_email(self):
        registered = self.request_reset("student@eafit.edu.co")
        unknown = self.request_reset("nobody@eafit.edu.co")

        self.assertEqual(registered.redirect_chain, unknown.redirect_chain)
        self.assertContains(unknown, "If an account exists for that institutional email")
        self.assertEqual(len(mail.outbox), 1)

    # Given a valid link, when the user enters a new password twice, then the
    # system saves it and the user can log in with it.
    def test_reset_link_sets_a_new_password(self):
        self.request_reset("student@eafit.edu.co")

        form_page = self.client.get(self.reset_link(), follow=True)
        response = self.client.post(
            form_page.redirect_chain[-1][0],
            {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
            follow=True,
        )

        self.assertContains(response, "Your password was changed.")
        self.assertTrue(self.can_login(NEW_PASSWORD))
        self.client.logout()
        self.assertFalse(self.can_login(PASSWORD))

    # Given a recovery link, when it has already been used, then the system
    # rejects it and offers to request a new one.
    def test_used_link_is_rejected(self):
        self.request_reset("student@eafit.edu.co")
        link = self.reset_link()
        form_page = self.client.get(link, follow=True)
        self.client.post(
            form_page.redirect_chain[-1][0],
            {"new_password1": NEW_PASSWORD, "new_password2": NEW_PASSWORD},
        )

        response = self.client.get(link, follow=True)

        self.assertContains(response, "This link no longer works.")
        self.assertContains(response, reverse("accounts:password_reset"))

    # Given a recovery link, when it has expired, then the system rejects it.
    def test_expired_link_is_rejected(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 60 * 60 * 24)
        self.request_reset("student@eafit.edu.co")
        link = self.reset_link()
        later = PasswordResetTokenGenerator()._now() + timedelta(days=2)

        with patch.object(PasswordResetTokenGenerator, "_now", return_value=later):
            response = self.client.get(link, follow=True)

        self.assertContains(response, "This link no longer works.")

    # Given an inactive account, when a recovery is requested, then no email
    # is sent and the account still cannot log in.
    def test_inactive_account_gets_no_reset_email(self):
        self.user.is_active = False
        self.user.save()

        self.request_reset("student@eafit.edu.co")

        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(self.can_login(PASSWORD))


class PasswordChangeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student@eafit.edu.co",
            email="student@eafit.edu.co",
            password=PASSWORD,
        )
        self.url = reverse("accounts:password_change")

    def change(self, old, new1, new2):
        return self.client.post(
            self.url,
            {"old_password": old, "new_password1": new1, "new_password2": new2},
        )

    # Only a logged-in user can change the password.
    def test_change_password_requires_login(self):
        response = self.client.get(self.url)

        self.assertRedirects(response, f"{reverse('accounts:login')}?next={self.url}")

    # Given a logged-in user, when they enter their current password and a
    # new valid password twice, then the password changes and the session
    # stays open.
    def test_logged_in_user_changes_password_and_stays_logged_in(self):
        self.client.login(username=self.user.username, password=PASSWORD)

        response = self.change(PASSWORD, NEW_PASSWORD, NEW_PASSWORD)

        self.assertRedirects(response, reverse("accounts:password_change_done"))
        self.assertTrue(self.client.get(reverse("home")).wsgi_request.user.is_authenticated)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    # Given a logged-in user, when the current password is wrong or the new
    # passwords do not match, then nothing changes and a clear error appears.
    def test_wrong_current_password_or_mismatch_changes_nothing(self):
        self.client.login(username=self.user.username, password=PASSWORD)

        for old, new2 in (("WrongPass999", NEW_PASSWORD), (PASSWORD, "Different-2026")):
            with self.subTest(old=old, new2=new2):
                response = self.change(old, NEW_PASSWORD, new2)

                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(PASSWORD))

    # The account pages offer the change password page.
    def test_account_pages_link_to_change_password(self):
        self.client.login(username=self.user.username, password=PASSWORD)

        response = self.client.get(reverse("reports:my_reports"))

        self.assertContains(response, self.url)
