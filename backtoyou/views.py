"""Vistas del sitio que no son de ninguna app."""

from urllib.parse import urlsplit

from django.utils import translation
from django.views.i18n import set_language as django_set_language


def set_language(request):
    """El set_language de Django, para el selector de idioma de la cabecera.

    Django cambia el idioma de "next" (/es/reports/ -> /en/reports/) solo si
    "next" esta en el idioma activo, que en esta direccion sin prefijo sale
    de la cookie o del navegador. Con un enlace compartido en el otro idioma
    no la reconocia y la persona se quedaba en la misma pagina. Por eso se
    activa primero el idioma de "next".
    """
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    language = translation.get_language_from_path(urlsplit(next_url).path)
    if language:
        translation.activate(language)
    return django_set_language(request)
