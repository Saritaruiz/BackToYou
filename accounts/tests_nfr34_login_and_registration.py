"""NFR34 - Security and Privacy: un login que no ayuda a un atacante.

- Despues de 5 intentos fallidos con el mismo correo, el login se bloquea
  15 minutos, exista o no la cuenta.
- La cuenta nueva queda activa al registrarse. Se probo activarla con un
  enlace por correo, pero el filtro de seguridad del correo de EAFIT abre
  los enlaces solo, asi que no comprobaba nada. El correo queda para
  recuperar la contrasena (RF39) y para los avisos (RF15).
- RF01/RF39: el registro muestra las reglas de la contrasena y se puede ver
  lo que se escribe.
"""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import LoginFailure, User


PASSWORD = "StrongPass123"


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


class RegistrationTests(TestCase):
    def register(self, email):
        return self.client.post(
            reverse("accounts:register"),
            {"full_name": "New Member", "email": email, "password1": PASSWORD, "password2": PASSWORD},
        )

    def test_a_new_account_can_log_in_right_away(self):
        self.register("new@eafit.edu.co")

        self.assertTrue(User.objects.get(email="new@eafit.edu.co").is_active)
        self.client.post(reverse("accounts:login"), {"username": "new@eafit.edu.co", "password": PASSWORD})
        self.assertIn("_auth_user_id", self.client.session)

    def test_a_repeated_email_offers_to_log_in_or_reset_the_password(self):
        User.objects.create_user("taken@eafit.edu.co", "taken@eafit.edu.co", PASSWORD)

        response = self.register("taken@eafit.edu.co")

        self.assertContains(response, "already registered")
        self.assertContains(response, reverse("accounts:password_reset"))


class PasswordFieldsTests(TestCase):
    def test_registration_shows_the_password_rules_before_any_error(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertContains(response, "at least 8 characters")
        self.assertContains(response, "Show password")

    def test_login_lets_you_see_the_password(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertContains(response, "Show password")
