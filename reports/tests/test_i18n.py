"""i18n: la interfaz en espanol y en ingles, con el idioma en la URL.

Los textos fuente estan en ingles (el resto de las pruebas los usan); aqui se
pide el espanol de forma explicita con /es/ o translation.override("es").
"""

import re
import struct
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from accounts.models import User

from ..models import Category, ItemReport
from .test_nfr38_editorial_design import FrozenDatetime
from .test_rf22_ai_description import FakeOllama, png_upload


LOCALE = Path(settings.BASE_DIR) / "locale" / "es" / "LC_MESSAGES"
PASSWORD = "StrongPass123"


def spanish(name, *args):
    with translation.override("es"):
        return reverse(name, args=args)


class I18nTestCase(TestCase):
    """Cada prueba deja el idioma como lo encontro.

    LocaleMiddleware activa el idioma de cada peticion y, en el hilo de las
    pruebas, queda activo para las siguientes, que esperan el ingles.
    """

    def setUp(self):
        super().setUp()
        self.addCleanup(translation.deactivate)


class LanguageInUrlTests(I18nTestCase):
    def test_root_redirects_to_the_language_of_the_browser(self):
        for accept, prefix in (("es-CO,es;q=0.9", "/es/"), ("en-US,en;q=0.9", "/en/")):
            with self.subTest(accept=accept):
                response = self.client.get("/", HTTP_ACCEPT_LANGUAGE=accept)

                self.assertRedirects(response, prefix, fetch_redirect_response=False)

    @override_settings(LANGUAGE_CODE="es")
    def test_any_other_language_gets_spanish(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="pt-BR,pt;q=0.9")

        self.assertRedirects(response, "/es/", fetch_redirect_response=False)

    # Un enlace viejo, sin idioma, no es una pagina que no existe.
    def test_old_links_without_the_language_still_work(self):
        response = self.client.get(
            "/reports/", HTTP_ACCEPT_LANGUAGE="es", HTTP_ACCEPT="text/html,application/xhtml+xml"
        )

        self.assertRedirects(response, "/es/reports/", fetch_redirect_response=False)
        self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_each_page_says_its_language(self):
        self.assertContains(self.client.get("/es/"), '<html lang="es">', html=False)
        self.assertContains(self.client.get("/en/"), '<html lang="en">', html=False)

    def test_the_same_page_in_each_language(self):
        spanish_home = self.client.get("/es/")
        english_home = self.client.get("/en/")

        self.assertContains(spanish_home, "¿Qué <em>perdiste?</em>", html=False)
        self.assertContains(spanish_home, "Reportar un objeto perdido")
        self.assertContains(english_home, "What did you <em>lose?</em>", html=False)
        self.assertContains(english_home, "Report a lost item")

    def test_links_stay_in_the_language_of_the_page(self):
        response = self.client.get("/es/")

        self.assertContains(response, 'href="/es/reports/"', html=False)
        self.assertNotContains(response, 'href="/en/reports/"', html=False)


class LanguageSwitchTests(I18nTestCase):
    def test_header_offers_both_languages_and_marks_the_current_one(self):
        response = self.client.get("/es/reports/")

        self.assertContains(response, f'action="{reverse("set_language")}"', html=False)
        self.assertContains(response, 'name="next" type="hidden" value="/es/reports/"', html=False)
        self.assertContains(
            response, 'value="es" lang="es" aria-label="Español" aria-current="true">ES</button>', html=False
        )
        self.assertContains(response, 'value="en" lang="en" aria-label="English">EN</button>', html=False)

    def test_switching_returns_to_the_same_page_in_the_other_language(self):
        response = self.client.post(reverse("set_language"), {"language": "en", "next": "/es/reports/?q=llaves"})

        self.assertRedirects(response, "/en/reports/?q=llaves", fetch_redirect_response=False)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "en")

    def test_the_chosen_language_is_remembered(self):
        self.client.post(reverse("set_language"), {"language": "es", "next": "/en/"})

        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="en")

        self.assertRedirects(response, "/es/", fetch_redirect_response=False)

    def test_switch_is_there_for_logged_in_users_too(self):
        user = User.objects.create_user("sara@eafit.edu.co", "sara@eafit.edu.co", PASSWORD)
        self.client.force_login(user)

        self.assertContains(self.client.get(spanish("reports:my_reports")), 'class="language-switch"', html=False)


class SpanishContentTests(I18nTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            "sara@eafit.edu.co", "sara@eafit.edu.co", PASSWORD, first_name="Sara"
        )
        self.admin = User.objects.create_user(
            "admin@eafit.edu.co", "admin@eafit.edu.co", PASSWORD, role=User.Role.ADMINISTRATOR
        )
        self.keys = Category.objects.create(name="Keys")
        self.report = ItemReport.objects.create(
            title="House keys",
            description="Three keys on a green keyring",
            category=self.keys,
            event_date="2026-08-10",
            location="Library",
            creator=self.user,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )

    def test_masthead_date_is_written_in_spanish(self):
        with mock.patch("django.template.defaulttags.datetime", FrozenDatetime):
            response = self.client.get("/es/")

        self.assertContains(response, "jueves, 22 de octubre de 2026")

    def test_type_and_status_are_translated(self):
        response = self.client.get(spanish("reports:report_detail", self.report.id))

        self.assertContains(response, '<span class="type-pill type-lost">Perdido</span>', html=False)
        self.assertContains(response, '<span class="status-pill status-active">Activo</span>', html=False)

    # Las categorias por defecto (seed_categories) se ven traducidas.
    def test_default_categories_are_shown_in_spanish(self):
        self.assertContains(self.client.get("/es/reports/"), "<span>Llaves</span>", html=False)
        self.assertContains(self.client.get("/en/reports/"), "<span>Keys</span>", html=False)

        self.client.force_login(self.user)
        form = self.client.get(spanish("reports:create_lost_report"))
        self.assertContains(form, f'<option value="{self.keys.id}">Llaves</option>', html=False)

    def test_admin_edits_the_category_name_as_it_is_saved(self):
        self.client.force_login(self.admin)

        response = self.client.get(spanish("administration_category_list"))

        self.assertContains(response, "<td>Keys</td>", html=False)

    def test_searching_the_spanish_category_name_finds_its_reports(self):
        response = self.client.get("/es/reports/", {"q": "llaves"})

        self.assertEqual(list(response.context["reports"]), [self.report])

    def test_form_errors_and_messages_are_in_spanish(self):
        self.client.force_login(self.user)

        response = self.client.post(
            spanish("reports:create_lost_report"),
            {
                "title": "Llaves",
                "description": "Tres llaves",
                "category": self.keys.id,
                "event_date": "2999-01-01",
                "location": "Biblioteca",
            },
        )
        self.assertContains(response, "La fecha no puede ser futura.")

        response = self.client.post(
            spanish("reports:mark_report_recovered", self.report.id), follow=True
        )
        self.assertContains(response, "El objeto quedó marcado como recuperado.")

    # Una cuenta es "activa" y un reporte "activo".
    def test_account_status_agrees_in_gender(self):
        self.client.force_login(self.admin)

        response = self.client.get(spanish("administration_user_list"))

        self.assertContains(response, "<td>Activa</td>", html=False)

    def test_password_rules_use_the_same_tone_as_the_rest(self):
        response = self.client.get(spanish("accounts:register"))

        self.assertContains(response, "Tu contraseña debe tener al menos 8 caracteres.")
        self.assertNotContains(response, "Su contraseña")


@override_settings(
    OLLAMA_HOST="http://ollama.test:11434",
    OLLAMA_VISION_MODEL="test-vision",
    GEMINI_API_KEY="",
)
class AISuggestionLanguageTests(I18nTestCase):
    def setUp(self):
        super().setUp()
        user = User.objects.create_user("sara@eafit.edu.co", "sara@eafit.edu.co", PASSWORD)
        self.client.force_login(user)
        Category.objects.create(name="Bottles")
        self.ollama = FakeOllama()
        patcher = mock.patch("reports.ai_description.urlopen", self.ollama.urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def prompt_for(self, language):
        with translation.override(language):
            url = reverse("reports:ai_describe_item")
        self.client.post(url, {"image": png_upload(), "report_type": "FOUND"})
        return self.ollama.chat_requests[-1][1]["messages"][0]["content"]

    # La IA escribe en el idioma de la pagina; la instruccion sigue en ingles.
    def test_suggestion_is_written_in_the_language_of_the_page(self):
        self.assertIn("Write the title and description in Spanish.", self.prompt_for("es"))
        self.assertIn("Write the title and description in English.", self.prompt_for("en"))
        self.assertIn("Report type: Found item.", self.prompt_for("es"))


class CatalogTests(TestCase):
    def test_every_text_has_its_spanish_translation(self):
        po = (LOCALE / "django.po").read_text(encoding="utf-8")

        self.assertNotIn("#, fuzzy", po)
        # Un msgstr vacio que no sigue en la linea siguiente es un texto sin traducir.
        empty = re.findall(r'^(msgstr(?:\[\d\])? "")\n(?!")', po, flags=re.M)
        self.assertEqual(empty, [], "Hay textos sin traducir en django.po")

    # Si alguien agrega textos al .po y no compila, Django no los ve.
    def test_the_compiled_file_matches_the_po(self):
        po = (LOCALE / "django.po").read_text(encoding="utf-8")
        entries = len(re.findall(r'^msgid "', po, flags=re.M))
        mo = (LOCALE / "django.mo").read_bytes()
        magic, _revision, strings = struct.unpack("<Iii", mo[:12])

        self.assertEqual(magic, 0x950412DE)
        self.assertEqual(strings, entries, "Compila django.po: ver la seccion Traducciones del README")
