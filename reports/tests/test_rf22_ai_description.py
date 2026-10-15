"""RF22 - AI-Based Object Description.

Las pruebas nunca llaman a Ollama: urlopen se reemplaza por uno simulado,
asi que no necesitan tener Ollama instalado ni el modelo descargado.
"""

import base64
import io
import json
from unittest import mock
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from ..models import Category, ItemReport


def png_upload(name="item.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def model_reply(text=None, **suggestion):
    """Arma el texto que devolveria el modelo dentro de message.content."""
    if text is None:
        text = json.dumps(
            {
                "item_visible": True,
                "title": "Blue steel water bottle",
                "description": "Blue insulated bottle with a dented lid.",
                "category": "Bottles",
                **suggestion,
            }
        )
    return text


class FakeOllama:
    """Responde como la API de Ollama: /api/tags y /api/chat."""

    def __init__(self):
        self.installed = ["test-vision:latest"]
        self.reply = model_reply()
        self.chat_error = None
        self.tags_error = None
        self.chat_requests = []

    def urlopen(self, request, timeout):
        if request.full_url.endswith("/api/tags"):
            if self.tags_error:
                raise self.tags_error
            body = {"models": [{"name": name} for name in self.installed]}
        else:
            self.chat_requests.append((request, json.loads(request.data), timeout))
            if self.chat_error:
                raise self.chat_error
            body = {"message": {"role": "assistant", "content": self.reply}}
        return io.BytesIO(json.dumps(body).encode("utf-8"))


@override_settings(
    OLLAMA_HOST="http://ollama.test:11434",
    OLLAMA_VISION_MODEL="test-vision",
    OLLAMA_TIMEOUT=30,
)
class AIDescriptionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="reporter@eafit.edu.co",
            email="reporter@eafit.edu.co",
            password="StrongPass123",
        )
        self.bottles = Category.objects.create(name="Bottles")
        Category.objects.create(name="Electronics")
        self.client.login(username=self.user.email, password="StrongPass123")
        self.url = reverse("reports:ai_describe_item")

        self.ollama = FakeOllama()
        patcher = mock.patch("reports.ai_description.urlopen", self.ollama.urlopen)
        patcher.start()
        self.addCleanup(patcher.stop)

    def post_image(self, image=None, report_type="FOUND"):
        return self.client.post(
            self.url,
            {"image": image or png_upload(), "report_type": report_type},
        )

    def test_valid_image_returns_title_description_and_category(self):
        response = self.post_image()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "title": "Blue steel water bottle",
                "description": "Blue insulated bottle with a dented lid.",
                "category_id": self.bottles.id,
            },
        )

    def test_request_sends_photo_report_type_and_existing_categories(self):
        image = png_upload()
        expected_image = base64.b64encode(image.read()).decode("ascii")
        image.seek(0)

        self.post_image(image=image, report_type="LOST")

        request, payload, timeout = self.ollama.chat_requests[0]
        self.assertEqual(request.full_url, "http://ollama.test:11434/api/chat")
        self.assertEqual(timeout, 30)
        self.assertEqual(payload["model"], "test-vision")
        self.assertFalse(payload["stream"])
        message = payload["messages"][0]
        self.assertIn("Report type: Lost item.", message["content"])
        self.assertIn("Available categories: Bottles, Electronics.", message["content"])
        self.assertEqual(message["images"], [expected_image])
        self.assertEqual(
            payload["format"]["properties"]["category"]["enum"],
            ["Bottles", "Electronics", ""],
        )

    def test_json_wrapped_in_markdown_is_accepted(self):
        payload = json.dumps(
            {"item_visible": True, "title": "Keys", "description": "Two keys.", "category": ""}
        )
        self.ollama.reply = f"Here is the report:\n```json\n{payload}\n```"

        response = self.post_image()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Keys")

    def test_suggestion_does_not_create_a_report(self):
        self.post_image()

        self.assertFalse(ItemReport.objects.exists())

    def test_unknown_category_is_left_for_the_user(self):
        self.ollama.reply = model_reply(category="Furniture")

        response = self.post_image()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["category_id"])

    def test_empty_category_is_left_for_the_user(self):
        self.ollama.reply = model_reply(category="")

        response = self.post_image()

        self.assertIsNone(response.json()["category_id"])

    def test_long_title_is_trimmed_to_model_limit(self):
        self.ollama.reply = model_reply(title="x" * 300)

        response = self.post_image()

        self.assertEqual(len(response.json()["title"]), 150)

    def test_ai_service_error_shows_informative_message(self):
        self.ollama.chat_error = URLError("connection refused")

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("fill in the report manually", response.json()["error"])

    def test_ai_timeout_shows_informative_message(self):
        self.ollama.chat_error = TimeoutError("too slow")

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("fill in the report manually", response.json()["error"])

    def test_response_without_json_shows_informative_message(self):
        self.ollama.reply = "I see a bottle."

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("fill in the report manually", response.json()["error"])

    def test_image_without_clear_item_shows_informative_message(self):
        self.ollama.reply = model_reply(item_visible=False)

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("could not identify an item", response.json()["error"])

    def test_missing_image_is_rejected_without_calling_ai(self):
        response = self.client.post(self.url, {"report_type": "LOST"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.ollama.chat_requests, [])

    def test_unsupported_image_format_is_rejected_without_calling_ai(self):
        gif = SimpleUploadedFile("item.gif", b"GIF89a", content_type="image/gif")

        response = self.post_image(image=gif)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported image format", response.json()["error"])
        self.assertEqual(self.ollama.chat_requests, [])

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.post_image()

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertEqual(self.ollama.chat_requests, [])

    def test_get_request_is_not_allowed(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    @override_settings(OLLAMA_VISION_MODEL="")
    def test_ai_not_configured_returns_informative_message(self):
        response = self.post_image()

        self.assertEqual(response.status_code, 503)
        self.assertIn("not available", response.json()["error"])
        self.assertEqual(self.ollama.chat_requests, [])

    def test_ollama_not_running_returns_informative_message(self):
        self.ollama.tags_error = URLError("connection refused")

        response = self.post_image()

        self.assertEqual(response.status_code, 503)
        self.assertIn("not available", response.json()["error"])
        self.assertEqual(self.ollama.chat_requests, [])

    def test_model_not_downloaded_returns_informative_message(self):
        self.ollama.installed = ["llama3.2:latest"]

        response = self.post_image()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.ollama.chat_requests, [])

    @override_settings(OLLAMA_VISION_MODEL="test-vision:latest")
    def test_model_name_with_tag_is_recognized(self):
        response = self.post_image()

        self.assertEqual(response.status_code, 200)

    def test_create_form_shows_ai_suggestion_button(self):
        response = self.client.get(reverse("reports:create_lost_report"))

        self.assertContains(response, reverse("reports:ai_describe_item"))
        self.assertFalse(self.ai_button_is_disabled(response))

    @override_settings(OLLAMA_VISION_MODEL="")
    def test_create_form_disables_ai_button_when_not_configured(self):
        response = self.client.get(reverse("reports:create_found_report"))

        self.assertTrue(self.ai_button_is_disabled(response))
        self.assertContains(response, "AI suggestions are not available right now")
        self.assertNotContains(response, reverse("reports:ai_describe_item"))

    def test_create_form_disables_ai_button_when_ollama_is_not_running(self):
        self.ollama.tags_error = URLError("connection refused")

        response = self.client.get(reverse("reports:create_found_report"))

        self.assertTrue(self.ai_button_is_disabled(response))

    def ai_button_is_disabled(self, response):
        html = response.content.decode()
        start = html.index('id="ai-suggest"')
        return "disabled" in html[start:html.index(">", start)]
