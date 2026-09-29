"""RF22 - AI-Based Object Description.

Envia la foto del objeto a un modelo de vision de Hugging Face (Inference
Providers) y devuelve una sugerencia de titulo, descripcion y categoria.
Sigue el taller de IA del curso: el token se lee de huggingface.env con
python-dotenv (ver settings.py).

La sugerencia nunca crea el reporte: solo llena el formulario para que el
usuario la revise, la corrija y la envie.
"""

import base64
import json
import logging
import re

import httpx2
from django.conf import settings
from huggingface_hub import InferenceClient


logger = logging.getLogger(__name__)

TITLE_MAX_LENGTH = 150  # igual que ItemReport.title

INSTRUCTION = (
    "You help members of the EAFIT university community write lost and found "
    "reports. Look at the photo and describe the item so its owner can "
    "recognize it: type of object, brand if visible, color, size, material and "
    "distinctive marks such as stickers, scratches or cases. "
    "Write in English, in a neutral tone. The title must be short (under 10 "
    "words). The description must be 2 to 4 sentences. "
    "Never transcribe personal data visible in the photo, such as names, "
    "document or student ID numbers, phone numbers, emails or addresses; "
    "mention only that the item shows personal information. "
    "Choose the category only from the list provided. If none fits, use an "
    "empty string. If the photo does not clearly show an object, set "
    "item_visible to false.\n\n"
    "Answer with only a JSON object, with no text before or after it, using "
    'exactly these keys: {"item_visible": true, "title": "...", '
    '"description": "...", "category": "..."}'
)

# Algunos modelos envuelven el JSON en ```json ... ``` o agregan texto.
JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class AIDescriptionError(Exception):
    """Error que se le puede mostrar al usuario tal cual."""


def is_available():
    return bool(settings.HF_TOKEN)


def _parse_suggestion(text):
    match = JSON_OBJECT.search(text or "")
    if not match:
        raise ValueError("The model did not return a JSON object.")
    suggestion = json.loads(match.group())
    if not isinstance(suggestion, dict):
        raise ValueError("The model did not return a JSON object.")
    return suggestion


def describe_item_image(image_file, report_type_label, category_names):
    """Devuelve {"title", "description", "category"} a partir de la foto.

    `category` es el nombre de una de `category_names` o "" si ninguna encaja.
    Lanza AIDescriptionError si la IA no esta disponible o no reconoce un objeto.
    """
    if not is_available():
        raise AIDescriptionError(
            "AI suggestions are not available right now. Please fill in the report manually."
        )

    image_file.seek(0)
    encoded = base64.b64encode(image_file.read()).decode("ascii")
    content_type = getattr(image_file, "content_type", "") or "image/jpeg"

    prompt = (
        f"{INSTRUCTION}\n\n"
        f"Report type: {report_type_label} item.\n"
        f"Available categories: {', '.join(category_names) or 'none'}."
    )

    # El usuario espera con el formulario abierto: mejor fallar rapido y que
    # llene el reporte a mano que dejarlo minutos esperando.
    client = InferenceClient(provider="auto", api_key=settings.HF_TOKEN, timeout=45)
    try:
        response = client.chat.completions.create(
            model=settings.HF_VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
            max_tokens=400,
            temperature=0,
        )
        suggestion = _parse_suggestion(response.choices[0].message.content)
    except (httpx2.HTTPError, ValueError, TypeError, IndexError, AttributeError):
        # httpx2.HTTPError cubre los errores de huggingface_hub (token
        # invalido, sin creditos, modelo no disponible, tiempo agotado) y los
        # de red. ValueError cubre JSON invalido (json.JSONDecodeError).
        logger.exception("RF22: Hugging Face description request failed.")
        raise AIDescriptionError(
            "The AI service could not describe the image right now. "
            "Please fill in the report manually."
        )

    if not suggestion.get("item_visible"):
        raise AIDescriptionError(
            "We could not identify an item in this image. "
            "Try a clearer photo or fill in the report manually."
        )

    category = str(suggestion.get("category") or "")
    return {
        "title": str(suggestion.get("title") or "").strip()[:TITLE_MAX_LENGTH],
        "description": str(suggestion.get("description") or "").strip(),
        "category": category if category in category_names else "",
    }
