"""Shared public visibility and RF24 publication ordering."""
from django.db.models import Count, Max, Prefetch, Q
from django.db.models.functions import Coalesce

from .models import ItemReport, ReportFlag


def public_reports():
    return ItemReport.objects.filter(status=ItemReport.Status.ACTIVE)


def open_flags():
    """RF43: avisos que ningun administrador ha revisado todavia."""
    return ReportFlag.objects.filter(reviewed_at__isnull=True)


def flagged_reports():
    """RF43: reportes publicados con avisos abiertos, los mas avisados primero.

    Cada reporte trae open_flag_count y sus avisos abiertos en open_flag_list,
    en un numero fijo de consultas.
    """
    is_open = Q(flags__reviewed_at__isnull=True)
    return (
        public_reports()
        .annotate(
            open_flag_count=Count("flags", filter=is_open),
            last_flagged_at=Max("flags__created_at", filter=is_open),
        )
        .filter(open_flag_count__gt=0)
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "flags",
                queryset=open_flags().order_by("-created_at", "-id"),
                to_attr="open_flag_list",
            )
        )
        .order_by("-open_flag_count", "-last_flagged_at", "-id")
    )


def recent_public_reports():
    return (
        public_reports()
        .select_related("category")
        .annotate(published_at=Coalesce("moderated_at", "created_at"))
        .order_by("-published_at", "-id")[:6]
    )
