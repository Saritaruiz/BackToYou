"""RF22 - AI-Based Object Description.

Las pruebas nunca llaman a Hugging Face: el cliente se reemplaza por uno
simulado, asi que no necesitan token ni internet.
"""

import io
import json
from types import SimpleNamespace
from unittest import mock

import httpx2
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from huggingface_hub.errors import InferenceTimeoutError
from PIL import Image

from ..models import Category, ItemReport


def png_upload(name="item.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def model_reply(text=None, **suggestion):
    """Arma la respuesta que devolveria client.chat.completions.create."""
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
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@override_settings(HF_TOKEN="hf_test", HF_VISION_MODEL="test/vision-model")
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

        patcher = mock.patch("reports.ai_description.InferenceClient")
        self.client_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.create_completion = self.client_class.return_value.chat.completions.create
        self.create_completion.return_value = model_reply()

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
        self.post_image(report_type="LOST")

        self.assertEqual(self.client_class.call_args.kwargs["api_key"], "hf_test")
        kwargs = self.create_completion.call_args.kwargs
        self.assertEqual(kwargs["model"], "test/vision-model")
        text, image = kwargs["messages"][0]["content"]
        self.assertIn("Report type: Lost item.", text["text"])
        self.assertIn("Available categories: Bottles, Electronics.", text["text"])
        self.assertTrue(image["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_json_wrapped_in_markdown_is_accepted(self):
        payload = json.dumps(
            {"item_visible": True, "title": "Keys", "description": "Two keys.", "category": ""}
        )
        self.create_completion.return_value = model_reply(
            text=f"Here is the report:\n```json\n{payload}\n```"
        )

        response = self.post_image()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Keys")

    def test_suggestion_does_not_create_a_report(self):
        self.post_image()

        self.assertFalse(ItemReport.objects.exists())

    def test_unknown_category_is_left_for_the_user(self):
        self.create_completion.return_value = model_reply(category="Furniture")

        response = self.post_image()

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["category_id"])

    def test_empty_category_is_left_for_the_user(self):
        self.create_completion.return_value = model_reply(category="")

        response = self.post_image()

        self.assertIsNone(response.json()["category_id"])

    def test_long_title_is_trimmed_to_model_limit(self):
        self.create_completion.return_value = model_reply(title="x" * 300)

        response = self.post_image()

        self.assertEqual(len(response.json()["title"]), 150)

    def test_ai_service_error_shows_informative_message(self):
        self.create_completion.side_effect = httpx2.ConnectError("offline")

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("fill in the report manually", response.json()["error"])

    def test_ai_timeout_shows_informative_message(self):
        self.create_completion.side_effect = InferenceTimeoutError("too slow")

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("fill in the report manually", response.json()["error"])

    def test_response_without_json_shows_informative_message(self):
        self.create_completion.return_value = model_reply(text="I see a bottle.")

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("fill in the report manually", response.json()["error"])

    def test_image_without_clear_item_shows_informative_message(self):
        self.create_completion.return_value = model_reply(item_visible=False)

        response = self.post_image()

        self.assertEqual(response.status_code, 502)
        self.assertIn("could not identify an item", response.json()["error"])

    def test_missing_image_is_rejected_without_calling_ai(self):
        response = self.client.post(self.url, {"report_type": "LOST"})

        self.assertEqual(response.status_code, 400)
        self.create_completion.assert_not_called()

    def test_unsupported_image_format_is_rejected_without_calling_ai(self):
        gif = SimpleUploadedFile("item.gif", b"GIF89a", content_type="image/gif")

        response = self.post_image(image=gif)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Unsupported image format", response.json()["error"])
        self.create_completion.assert_not_called()

    def test_anonymous_user_is_redirected_to_login(self):
        self.client.logout()

        response = self.post_image()

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.create_completion.assert_not_called()

    def test_get_request_is_not_allowed(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    @override_settings(HF_TOKEN="")
    def test_ai_not_configured_returns_informative_message(self):
        response = self.post_image()

        self.assertEqual(response.status_code, 503)
        self.assertIn("not available", response.json()["error"])
        self.create_completion.assert_not_called()

    def test_create_form_shows_ai_suggestion_button(self):
        response = self.client.get(reverse("reports:create_lost_report"))

        self.assertContains(response, reverse("reports:ai_describe_item"))
        self.assertFalse(self.ai_button_is_disabled(response))

    @override_settings(HF_TOKEN="")
    def test_create_form_disables_ai_button_when_not_configured(self):
        response = self.client.get(reverse("reports:create_found_report"))

        self.assertTrue(self.ai_button_is_disabled(response))
        self.assertContains(response, "AI suggestions are not available right now")
        self.assertNotContains(response, reverse("reports:ai_describe_item"))

    def ai_button_is_disabled(self, response):
        html = response.content.decode()
        start = html.index('id="ai-suggest"')
        return "disabled" in html[start:html.index(">", start)]
