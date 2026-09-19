"""RF19: una cuenta desactivada pierde acceso de inmediato, no solo al
volver a iniciar sesion.

Django deniega el LOGIN de una cuenta inactiva por defecto, pero no revisa
is_active en cada peticion, asi que una sesion abierta ANTES de desactivar
la cuenta seguiria funcionando hasta que la persona cerrara sesion por su
cuenta. Este middleware cierra esa sesion en la siguiente peticion.
"""

from django.contrib.auth import logout


def enforce_active_account(get_response):
    def middleware(request):
        if request.user.is_authenticated and not request.user.is_active:
            logout(request)

        return get_response(request)

    return middleware
