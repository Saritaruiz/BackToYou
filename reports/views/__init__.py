"""Vistas de la app reports, separadas por responsabilidad.

Cada modulo agrupa los requisitos de un mismo frente para que dos personas
puedan trabajar en paralelo sin editar el mismo archivo.
"""

from .activity_log import activity_log
from .categories import (
    category_create,
    category_delete,
    category_edit,
    category_list,
)
from .create import create_found_report, create_lost_report
from .flags import (
    flag_report,
    flagged_report_list,
    remove_flagged_report,
    review_flagged_report,
)
from .moderation import (
    delete_pending_report,
    edit_pending_report,
    moderate_report_detail,
    pending_report_list,
)
from .owner import (
    delete_report,
    edit_report,
    mark_report_recovered,
    my_reports,
)
from .public import contact_reporter, report_detail, report_list

__all__ = [
    "activity_log",
    "category_create",
    "category_delete",
    "category_edit",
    "category_list",
    "contact_reporter",
    "create_found_report",
    "create_lost_report",
    "delete_pending_report",
    "delete_report",
    "edit_pending_report",
    "edit_report",
    "flag_report",
    "flagged_report_list",
    "mark_report_recovered",
    "moderate_report_detail",
    "my_reports",
    "pending_report_list",
    "remove_flagged_report",
    "report_detail",
    "report_list",
    "review_flagged_report",
]
