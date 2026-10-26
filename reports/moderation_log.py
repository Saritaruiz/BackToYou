"""RF44 Moderation Activity Log.

Cada vista de moderacion registra su accion con una sola linea:

    log_action(request.user, ModerationLogEntry.Action.APPROVED, report)

Asi, quien agregue otra accion de moderacion solo tiene que sumar esa linea.
"""

from .models import ModerationLogEntry


def log_action(administrator, action, report, details=""):
    # Se llama antes de eliminar un reporte, para copiar su titulo; despues,
    # la entrada queda sin enlace al reporte pero con el titulo.
    return ModerationLogEntry.objects.create(
        action=action,
        administrator=administrator,
        administrator_email=administrator.email,
        report=report,
        report_title=report.title,
        details=details,
    )
