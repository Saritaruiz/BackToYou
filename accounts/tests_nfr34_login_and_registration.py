"""NFR34 - Security and Privacy: login y registro que no ayudan a un atacante.

- Despues de 5 intentos fallidos con el mismo correo, el login se bloquea
  15 minutos, exista o no la cuenta.
- El registro responde igual tenga o no cuenta el correo, y la cuenta nueva
  queda inactiva hasta abrir el enlace que llega a ese correo.
- RF01/RF39: el registro muestra las reglas de la contrasena y se puede ver
  lo que se escribe.
"""

import re
from datetime import timedelta

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import LoginFailure, User
from .tokens import account_activation_token


PASSWORD = "StrongPass123"
ACTIVATION_LINK = re.compile(r"https?://\S+/accounts/activate/\S+/")


class LoginAttemptLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="owner@eafit.edu.co",
            email="owner@eafit.edu.co",
            password=PASSWORD,
        )

    def login(self, email, password):
        return self.client.post(reverse("accounts:login"), {"username": email, "password": password})

    def fail(self, email, times):
        for attempt in range(times):
            self.login(email, f"WrongPass{attempt}")

    def is_logged_in(self):
        return "_auth_user_id" in self.client.session

    def test_five_failed_attempts_lock_the_email_even_with_the_right_password(self):
        self.fail("owner@eafit.edu.co", 5)

        response = self.login("owner@eafit.edu.co", PASSWORD)

        self.assertContains(response, "Too many failed attempts")
        self.assertFalse(self.is_logged_in())

    def test_four_failed_attempts_still_allow_the_right_password(self):
        self.fail("owner@eafit.edu.co", 4)

        self.login("owner@eafit.edu.co", PASSWORD)

        self.assertTrue(self.is_logged_in())

    def test_the_lock_does_not_reveal_whether_the_account_exists(self):
        self.fail("nobody@eafit.edu.co", 5)

        response = self.login("nobody@eafit.edu.co", "AnyPass123")

        self.assertContains(response, "Too many failed attempts")

    def test_a_successful_login_clears_previous_failures(self):
        self.fail("owner@eafit.edu.co", 4)
        self.login("owner@eafit.edu.co", PASSWORD)

        self.assertFalse(LoginFailure.objects.filter(email="owner@eafit.edu.co").exists())

    def test_failures_older_than_the_lock_window_do_not_count(self):
        self.fail("owner@eafit.edu.co", 5)
        LoginFailure.objects.update(created_at=timezone.now() - timedelta(minutes=16))

        self.login("owner@eafit.edu.co", PASSWORD)

        self.assertTrue(self.is_logged_in())

    def test_the_lock_applies_only_to_that_email(self):
        User.objects.create_user("other@eafit.edu.co", "other@eafit.edu.co", PASSWORD)
        self.fail("owner@eafit.edu.co", 5)

        self.login("other@eafit.edu.co", PASSWORD)

        self.assertTrue(self.is_logged_in())

    def test_the_email_is_compared_without_case(self):
        self.fail("OWNER@eafit.edu.co", 5)

        response = self.login("owner@eafit.edu.co", PASSWORD)

        self.assertContains(response, "Too many failed attempts")


class RegistrationActivationTests(TestCase):
    def register(self, email="new@eafit.edu.co", password=PASSWORD, name="New Member"):
        return self.client.post(
            reverse("accounts:register"),
            {"full_name": name, "email": email, "password1": password, "password2": password},
        )

    def last_activation_link(self):
        return ACTIVATION_LINK.search(mail.outbox[-1].body).group()

    def login(self, email, password):
        self.client.post(reverse("accounts:login"), {"username": email, "password": password})
        return "_auth_user_id" in self.client.session

    def test_a_new_account_stays_inactive_until_the_email_link_is_opened(self):
        response = self.register()

        self.assertRedirects(response, reverse("accounts:registration_sent"))
        user = User.objects.get(email="new@eafit.edu.co")
        self.assertFalse(user.is_active)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@eafit.edu.co"])
        self.assertIn("Activate", mail.outbox[0].subject)
        self.assertFalse(self.login("new@eafit.edu.co", PASSWORD))

        response = self.client.get(self.last_activation_link(), follow=True)

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertContains(response, "Your account is active")
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(self.login("new@eafit.edu.co", PASSWORD))

    def test_the_activation_link_works_only_once(self):
        self.register()
        link = self.last_activation_link()
        self.client.get(link)

        response = self.client.get(link)

        self.assertContains(response, "This link no longer works")

    def test_registering_an_existing_email_gives_the_same_answer(self):
        User.objects.create_user("taken@eafit.edu.co", "taken@eafit.edu.co", PASSWORD)

        response = self.register(email="TAKEN@eafit.edu.co", password="OtherPass456")

        self.assertRedirects(response, reverse("accounts:registration_sent"))
        self.assertEqual(User.objects.filter(email__iexact="taken@eafit.edu.co").count(), 1)
        # Solo quien abre ese correo sabe que la cuenta ya existia.
        self.assertEqual(mail.outbox[0].to, ["taken@eafit.edu.co"])
        self.assertIn("already has an account", mail.outbox[0].body)
        self.assertTrue(User.objects.get(email="taken@eafit.edu.co").check_password(PASSWORD))

    def test_registering_again_before_activating_replaces_the_password_and_old_links(self):
        # Alguien se registra con un correo ajeno; despues la duena del correo.
        self.register(password="IntruderPass789")
        intruder_link = self.last_activation_link()
        self.register(password=PASSWORD)
        owner_link = self.last_activation_link()

        self.assertContains(self.client.get(intruder_link), "This link no longer works")
        self.client.get(owner_link)

        self.assertFalse(self.login("new@eafit.edu.co", "IntruderPass789"))
        self.assertTrue(self.login("new@eafit.edu.co", PASSWORD))

    def test_a_link_does_not_reactivate_an_account_deactivated_by_an_administrator(self):
        admin = User.objects.create_user(
            "admin@eafit.edu.co", "admin@eafit.edu.co", PASSWORD, role=User.Role.ADMINISTRATOR
        )
        user = User.objects.create_user("member@eafit.edu.co", "member@eafit.edu.co", PASSWORD)
        user.is_active = False
        user.status_changed_by = admin
        user.save()
        link = reverse(
            "accounts:activate",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": account_activation_token.make_token(user),
            },
        )

        response = self.client.get(link)

        self.assertContains(response, "This link no longer works")
        user.refresh_from_db()
        self.assertFalse(user.is_active)

    def test_a_password_reset_link_does_not_activate_an_account(self):
        self.register()
        user = User.objects.get(email="new@eafit.edu.co")
        link = reverse(
            "accounts:activate",
            kwargs={
                "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
            },
        )

        self.assertContains(self.client.get(link), "This link no longer works")

    def test_a_non_institutional_email_still_shows_the_error(self):
        response = self.register(email="someone@gmail.com")

        self.assertContains(response, "@eafit.edu.co")
        self.assertFalse(User.objects.exists())
        self.assertEqual(mail.outbox, [])


class PasswordFieldsTests(TestCase):
    def test_registration_shows_the_password_rules_before_any_error(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertContains(response, "at least 8 characters")
        self.assertContains(response, "Show password")

    def test_login_lets_you_see_the_password(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, "Show password")
