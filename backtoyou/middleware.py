"""Avisos en vez de paginas de error cuando una persona navega.

Si alguien abre a mano una direccion que no le corresponde, la vista lanza
PermissionDenied (403) o Http404 como siempre. Para la navegacion normal en
el navegador, este middleware convierte eso en un aviso y devuelve a la
persona a la pagina donde estaba (o al inicio).

Las demas peticiones (pruebas, fetch del RF22, Django Admin) siguen
recibiendo el 403/404 de siempre con las paginas templates/403.html y 404.html.

El aviso del 404 es neutral a proposito: no dice "no tienes permiso" para no
revelar que existe un reporte oculto (ver reports/tests/test_error_pages.py).
"""

from urllib.parse import urlparse

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme


PERMISSION_MESSAGE = "You don't have permission to access that page."
NOT_AVAILABLE_MESSAGE = "That page is not available."


class FriendlyAccessErrorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Cubre todo 404: el Http404 de una vista y tambien las direcciones
        # que no existen, que Django resuelve antes de llegar a las vistas.
        if response.status_code == 404 and _is_browser_navigation(request):
            return _notice_and_go_back(request, NOT_AVAILABLE_MESSAGE)

        return response

    def process_exception(self, request, exception):
        if isinstance(exception, PermissionDenied) and _is_browser_navigation(request):
            return _notice_and_go_back(request, PERMISSION_MESSAGE)
        return None


def _notice_and_go_back(request, message):
    messages.error(request, message)
    return redirect(_safe_previous_page(request))


def _is_browser_navigation(request):
    # Los navegadores piden text/html al abrir una pagina; fetch y el
    # cliente de pruebas no, asi que conservan el codigo 403/404.
    if request.path.startswith("/admin/"):
        return False
    return "text/html" in request.headers.get("Accept", "")


def _safe_previous_page(request):
    referer = request.headers.get("Referer", "")
    is_same_site = url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    # Si la pagina anterior es la misma que fallo, volver a ella crearia un
    # ciclo de redirecciones: en ese caso se va al inicio.
    if referer and is_same_site and urlparse(referer).path != request.path:
        return referer
    return "home"
