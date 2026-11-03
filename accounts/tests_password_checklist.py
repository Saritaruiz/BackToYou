"""Registro: las reglas de la contrasena se marcan mientras se escribe.

La pagina muestra cada regla de AUTH_PASSWORD_VALIDATORS y le pregunta a
accounts:password_check cuales se cumplen. Esa vista usa la misma validacion
que el formulario (con el nombre y el correo escritos), asi que el chulo
coincide con lo que se acepta al enviar.
"""

from django.contrib.auth import password_validation
from django.test import Client, TestCase
from django.urls import reverse, reverse_lazy

from .models import User


# Orden de AUTH_PASSWORD_VALIDATORS: parecida a tus datos, minimo 8
# caracteres, comun, solo numeros.
STRONG = "Lluvia-Biblioteca-38"


class PasswordChecklistPageTests(TestCase):
    def test_register_page_lists_every_rule_and_the_match(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertContains(response, 'class="password-rules"', html=False)
        self.assertContains(response, f'data-check-url="{reverse("accounts:password_check")}"', html=False)
        for index, rule in enumerate(password_validation.password_validators_help_texts()):
            with self.subTest(rule=rule):
                self.assertContains(response, f'data-rule="{index}"', html=False)
                self.assertContains(response, rule, html=False)
        self.assertContains(response, 'data-rule="match"', html=False)
        self.assertContains(response, "Both passwords match.")

    # El lector de pantalla lee las reglas al entrar al campo de la contrasena.
    def test_the_rules_describe_the_password_field(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertContains(response, 'aria-describedby="id_password1_helptext"', html=False)
        self.assertContains(response, '<ul class="password-rules" id="id_password1_helptext"', html=False)

    def test_other_password_forms_keep_the_plain_rules(self):
        user = User.objects.create_user("sara@eafit.edu.co", "sara@eafit.edu.co", STRONG)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:password_change"))

        self.assertNotContains(response, 'class="password-rules"')
        self.assertContains(response, 'class="field-help" id="id_new_password1_helptext"', html=False)


class PasswordCheckTests(TestCase):
    url = reverse_lazy("accounts:password_check")

    def rules(self, password, **personal):
        response = self.client.post(self.url, {"password": password, **personal})
        self.assertEqual(response.status_code, 200)
        return response.json()["rules"]

    def test_each_rule_is_answered_in_order(self):
        self.assertEqual(self.rules("short"), [True, False, True, True])
        self.assertEqual(self.rules("12345678"), [True, True, False, False])
        self.assertEqual(self.rules(STRONG), [True, True, True, True])

    def test_similarity_uses_the_name_and_email_written_so_far(self):
        self.assertEqual(self.rules("isabelacevedo")[0], True)
        self.assertEqual(self.rules("isabelacevedo", full_name="Isabel Acevedo")[0], False)
        self.assertEqual(self.rules("isabel.acevedo@eafit", email="isabel.acevedo@eafit.edu.co")[0], False)

    def test_nothing_is_saved(self):
        self.rules(STRONG, full_name="Isabel Acevedo", email="isabel@eafit.edu.co")

        self.assertFalse(User.objects.exists())

    def test_only_post_is_allowed(self):
        self.assertEqual(self.client.get(self.url, {"password": STRONG}).status_code, 405)

    def test_it_needs_the_csrf_token_like_any_form(self):
        client = Client(enforce_csrf_checks=True)

        self.assertEqual(client.post(self.url, {"password": STRONG}).status_code, 403)


class RegistrationMatchesTheChecklistTests(TestCase):
    def register(self, password, full_name="Isabel Acevedo"):
        return self.client.post(
            reverse("accounts:register"),
            {
                "full_name": full_name,
                "email": "isabel@eafit.edu.co",
                "password1": password,
                "password2": password,
            },
        )

    # Antes el registro solo comparaba con el correo; ahora tambien con el
    # nombre, igual que la lista de la pagina.
    def test_password_similar_to_the_name_is_rejected(self):
        response = self.register("isabelacevedo")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())
        self.assertFormError(response.context["form"], "password2", "The password is too similar to the first name.")

    def test_password_that_meets_every_rule_is_accepted(self):
        response = self.register(STRONG)

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertTrue(User.objects.filter(email="isabel@eafit.edu.co").exists())
