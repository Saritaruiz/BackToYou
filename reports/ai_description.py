"""RF22 - AI-Based Object Description.

Envia la foto del objeto a un modelo de vision y devuelve una sugerencia de
titulo, descripcion y categoria. El modelo corre en uno de dos lugares:

- Google Gemini API, si hay una GEMINI_API_KEY. Es lo que usa el servidor de
  AWS, que no tiene memoria para correr el modelo. Ver gemini.env.example.
- Ollama, en el mismo computador, en cualquier otro caso. El modelo y la
  direccion se pueden cambiar en ollama.env (ver ollama.env.example).

La sugerencia nunca crea el reporte: solo llena el formulario para que el
usuario la revise, la corrija y la envie.
"""

import base64
import json
import logging
import re
from urllib.request import Request, urlopen

from django.conf import settings


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

# Segundos que espera el formulario para saber si Ollama esta corriendo.
# Encendido responde en milisegundos; apagado, Windows tarda en rechazar la
# conexion, asi que es mejor desactivar el boton que frenar el formulario.
AVAILABILITY_TIMEOUT = 1

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIDescriptionError(Exception):
    """Error que se le puede mostrar al usuario tal cual."""


def _uses_gemini():
    # Con una clave de Gemini la app no necesita Ollama.
    return bool(settings.GEMINI_API_KEY)


def _ollama(path, payload=None, timeout=AVAILABILITY_TIMEOUT):
    """Llama a la API de Ollama y devuelve la respuesta como diccionario."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        settings.OLLAMA_HOST.rstrip("/") + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _gemini(payload):
    """Llama a la API de Gemini y devuelve la respuesta como diccionario."""
    request = Request(
        GEMINI_URL.format(model=settings.GEMINI_MODEL),
        data=json.dumps(payload).encode("utf-8"),
        # La clave va en un encabezado y no en la URL, para que no quede
        # escrita en los registros de errores.
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.GEMINI_API_KEY,
        },
    )
    with urlopen(request, timeout=settings.GEMINI_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def is_available():
    """True si Gemini esta configurado, o si Ollama corre y tiene el modelo."""
    if _uses_gemini():
        # No se consulta a Google cada vez que se abre el formulario: con la
        # clave y el modelo basta. Si la clave falla, el error se ve al pedir
        # la sugerencia.
        return bool(settings.GEMINI_MODEL)

    model = settings.OLLAMA_VISION_MODEL
    if not model:
        return False
    try:
        installed = _ollama("/api/tags").get("models", [])
    except (OSError, ValueError, AttributeError):
        # OSError cubre Ollama apagado, sin red y tiempo agotado.
        return False
    names = {entry.get("name") for entry in installed if isinstance(entry, dict)}
    # "ollama pull gemma3" queda guardado como "gemma3:latest".
    return model in names or f"{model}:latest" in names


def _parse_suggestion(text):
    match = JSON_OBJECT.search(text or "")
    if not match:
        raise ValueError("The model did not return a JSON object.")
    suggestion = json.loads(match.group())
    if not isinstance(suggestion, dict):
        raise ValueError("The model did not return a JSON object.")
    return suggestion


def _ask_ollama(prompt, encoded_image, answer_format):
    response = _ollama(
        "/api/chat",
        {
            "model": settings.OLLAMA_VISION_MODEL,
            "messages": [{"role": "user", "content": prompt, "images": [encoded_image]}],
            "format": answer_format,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 400},
        },
        timeout=settings.OLLAMA_TIMEOUT,
    )
    return response["message"]["content"]


def _ask_gemini(prompt, encoded_image, mime_type, answer_format):
    response = _gemini(
        {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": mime_type, "data": encoded_image}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": answer_format,
            },
        }
    )
    # Los modelos que "piensan" pueden devolver partes con su razonamiento
    # (thought): solo interesa la respuesta.
    parts = response["candidates"][0]["content"]["parts"]
    return "".join(part.get("text", "") for part in parts if not part.get("thought"))


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
    # validate_report_image solo deja pasar JPG y PNG.
    mime_type = getattr(image_file, "content_type", "") or "image/jpeg"

    prompt = (
        f"{INSTRUCTION}\n\n"
        f"Report type: {report_type_label} item.\n"
        f"Available categories: {', '.join(category_names) or 'none'}."
    )

    # Ollama y Gemini obligan al modelo a responder con este JSON
    # (structured outputs).
    answer_format = {
        "type": "object",
        "properties": {
            "item_visible": {"type": "boolean"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "category": {"type": "string", "enum": [*category_names, ""]},
        },
        "required": ["item_visible", "title", "description", "category"],
    }

    try:
        # El usuario espera con el formulario abierto: si el modelo tarda
        # demasiado, mejor que llene el reporte a mano.
        if _uses_gemini():
            text = _ask_gemini(prompt, encoded, mime_type, answer_format)
        else:
            text = _ask_ollama(prompt, encoded, answer_format)
        suggestion = _parse_suggestion(text)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        # OSError cubre el servicio apagado o sin red, el tiempo agotado y
        # las respuestas HTTP de error: modelo no descargado en Ollama, clave
        # invalida o cupo agotado en Gemini. ValueError cubre JSON invalido
        # (json.JSONDecodeError). IndexError y KeyError, una respuesta que
        # Gemini bloqueo y llega sin texto.
        logger.exception("RF22: AI description request failed.")
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
