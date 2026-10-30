"""RF07 - Search Items: buscar sin importar tildes ni mayusculas.

SQLite solo ignora las mayusculas en letras sin tilde: "camara" no
encontraba "Cámara" y "cámara" no encontraba "CÁMARA". Aqui se registra en
SQLite una funcion que quita tildes y pasa a minusculas, y la busqueda
compara el texto ya normalizado de los dos lados.
"""

import unicodedata

from django.db.backends.signals import connection_created
from django.db.models import Func, TextField
from django.dispatch import receiver


SQL_FUNCTION = "bty_normalize"


def normalize(text):
    """"Cámara CANON" -> "camara canon". La ñ queda como n."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


@receiver(connection_created)
def register_normalize_function(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        connection.connection.create_function(SQL_FUNCTION, 1, normalize, deterministic=True)


class Normalized(Func):
    """El campo con el texto normalizado, para filtrar en la base de datos."""

    function = SQL_FUNCTION
    output_field = TextField()
