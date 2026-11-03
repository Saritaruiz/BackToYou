"""RF07 - Search Items: buscar sin importar tildes ni mayusculas.

SQLite solo ignora las mayusculas en letras sin tilde: "camara" no
encontraba "Cámara" y "cámara" no encontraba "CÁMARA". Aqui se registra en
SQLite una funcion que quita tildes y pasa a minusculas, y la busqueda
compara el texto ya normalizado de los dos lados.
"""

from heapq import heappush, heappushpop

import re
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


# FR41: palabras frecuentes que no identifican un objeto (ingles y espanol).
_MATCH_STOP_WORDS = frozenset(
    "a an and at by for from in is it my of on or the this to was with "
    "de del el en la las los mi para por que se sin su un una y "
    "lost found perdido perdida encontrado encontrada item objeto".split()
)


def _match_words(text):
    return {
        word for word in re.findall(r"[^\W_]+", normalize(text))
        if len(word) > 1 and word not in _MATCH_STOP_WORDS
    }


def _word_similarity(left, right):
    """Jaccard: proporcion de palabras compartidas, sin contar repeticiones."""
    union = left | right
    return len(left & right) / len(union) if union else 0


def possible_matches(report):
    """FR41: hasta cinco candidatos publicos, con un orden determinista.

    Exigimos Jaccard >= 0.25 en titulo + descripcion y dos palabras
    compartidas (o titulos normalizados identicos no vacios). Ubicacion y
    fecha nunca bastan para admitir un candidato. Puntuacion: 80% texto,
    15% ubicacion y hasta 5% por fechas separadas por menos de 30 dias.
    No hay corte por fecha: un objeto puede encontrarse mucho despues.
    La vista limita esta ayuda al propietario; aqui solo se leen datos
    publicos de candidatos. No hay consultas por candidato ni escrituras.
    """
    from .models import ItemReport
    from .querysets import public_reports

    opposite = {
        ItemReport.ReportType.LOST: ItemReport.ReportType.FOUND,
        ItemReport.ReportType.FOUND: ItemReport.ReportType.LOST,
    }.get(report.report_type)
    if opposite is None:
        return []

    title_words = _match_words(report.title)
    words = title_words | _match_words(report.description)
    if not words:
        return []
    location_words = _match_words(report.location)
    candidates = (
        public_reports()
        .filter(category_id=report.category_id, report_type=opposite)
        .exclude(pk=report.pk)
        .select_related("category")
    )
    ranked = []
    for candidate in candidates.iterator():
        candidate_title = _match_words(candidate.title)
        candidate_words = candidate_title | _match_words(candidate.description)
        text_score = _word_similarity(words, candidate_words)
        shared_words = words & candidate_words
        same_title = bool(title_words) and title_words == candidate_title
        if text_score < 0.25 or (len(shared_words) < 2 and not same_title):
            continue
        days = abs((report.event_date - candidate.event_date).days)
        score = (
            0.80 * text_score
            + 0.15 * _word_similarity(location_words, _match_words(candidate.location))
            + 0.05 * max(0, 1 - days / 30)
        )
        # NFR33: mantener solo los cinco mejores durante el recorrido.
        # La raiz es el peor; los desempates mantienen el orden de FR41.
        match = (score, -days, -candidate.pk, candidate)
        if len(ranked) < 5:
            heappush(ranked, match)
        else:
            heappushpop(ranked, match)

    return [match[3] for match in sorted(ranked, reverse=True)]
