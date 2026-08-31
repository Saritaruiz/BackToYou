"""Settings para correr la suite de tests.

Uso:
    python manage.py test --settings=backtoyou.test_settings

Django hashea cada contrasena con PBKDF2, que esta disenado para ser lento a
proposito. En produccion eso es lo correcto; en los tests, donde se crean
usuarios en cada setUp, es el 99% del tiempo de ejecucion. Con MD5 la suite
baja de minutos a segundos. MD5 solo se usa aqui, nunca en la aplicacion.
"""

from .settings import *  # noqa: F401,F403

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
