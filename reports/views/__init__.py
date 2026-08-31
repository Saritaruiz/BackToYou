"""Vistas de la app reports, separadas por responsabilidad.

Cada modulo agrupa los requisitos de un mismo frente para que dos personas
puedan trabajar en paralelo sin editar el mismo archivo.
"""

from .create import create_found_report, create_lost_report
from .moderation import moderate_report_detail, pending_report_list
from .owner import (
    delete_report,
    edit_report,
    mark_report_recovered,
    my_reports,
)
from .public import contact_reporter, report_detail, report_list

__all__ = [
    "contact_reporter",
    "create_found_report",
    "create_lost_report",
    "delete_report",
    "edit_report",
    "mark_report_recovered",
    "moderate_report_detail",
    "my_reports",
    "pending_report_list",
    "report_detail",
    "report_list",
]
