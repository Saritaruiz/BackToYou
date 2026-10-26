"""RF43 Flag Inappropriate Reports.

Cualquier usuario puede avisar a los administradores sobre un reporte ya
publicado que tenga informacion falsa, contenido ofensivo o datos personales.
El administrador revisa los avisos y los descarta o retira el reporte. El
creador nunca sabe quien aviso.
"""

from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import administrator_required

from ..email_notifications import notify_report_removed
from ..forms import ReportFlagForm
from ..models import ItemReport, ModerationLogEntry, ReportFlag
from ..moderation_log import log_action
from ..querysets import flagged_reports, open_flags


ALREADY_FLAGGED_MESSAGE = "You already flagged this report. An administrator will review it."


@login_required
def flag_report(request, report_id):
    report = get_object_or_404(
        ItemReport,
        id=report_id,
        status=ItemReport.Status.ACTIVE,
    )

    if report.creator == request.user:
        raise PermissionDenied("You cannot flag your own report.")

    if report.flags.filter(flagged_by=request.user).exists():
        messages.info(request, ALREADY_FLAGGED_MESSAGE)
        return redirect("reports:report_detail", report_id=report.id)

    if request.method == "POST":
        form = ReportFlagForm(request.POST)
        if form.is_valid():
            flag = form.save(commit=False)
            flag.report = report
            flag.flagged_by = request.user
            try:
                # Dos envios seguidos del mismo formulario: la base de datos
                # solo guarda el primero.
                with transaction.atomic():
                    flag.save()
            except IntegrityError:
                messages.info(request, ALREADY_FLAGGED_MESSAGE)
            else:
                messages.success(
                    request,
                    "Thank you. The report was flagged and an administrator will review it.",
                )
            return redirect("reports:report_detail", report_id=report.id)
    else:
        form = ReportFlagForm()

    return render(
        request,
        "reports/flag_report.html",
        {"form": form, "report": report},
    )


def _reason_summary(flags):
    """Motivos de los avisos con cuantas veces aparece cada uno."""
    counts = Counter(flag.get_reason_display() for flag in flags)
    return counts.most_common()


def _reason_text(flags):
    """Los motivos en una linea para el historial (RF44): "Personal data ×2"."""
    return " · ".join(
        f"{reason} ×{count}" if count > 1 else reason
        for reason, count in _reason_summary(flags)
    )


@administrator_required
def flagged_report_list(request):
    reports = list(flagged_reports())
    for report in reports:
        report.reason_summary = _reason_summary(report.open_flag_list)

    return render(
        request,
        "reports/flagged_report_list.html",
        {"reports": reports},
    )


def _get_flagged_report(report_id):
    """Un reporte publicado con avisos abiertos; si no, la pagina no existe."""
    report = get_object_or_404(
        ItemReport.objects.select_related("category"),
        id=report_id,
        status=ItemReport.Status.ACTIVE,
    )
    flags = list(open_flags().filter(report=report).order_by("-created_at", "-id"))
    if not flags:
        raise Http404("This report has no flags to review.")
    return report, flags


def _close_flags(report, administrator, reviewed_at):
    open_flags().filter(report=report).update(
        reviewed_by=administrator,
        reviewed_at=reviewed_at,
    )


@administrator_required
def review_flagged_report(request, report_id):
    report, flags = _get_flagged_report(report_id)

    if request.method == "POST":
        if request.POST.get("action") != "dismiss":
            raise PermissionDenied("Invalid review action.")

        with transaction.atomic():
            _close_flags(report, request.user, timezone.now())
            log_action(
                request.user,
                ModerationLogEntry.Action.FLAGS_DISMISSED,
                report,
                details=_reason_text(flags),
            )
        messages.success(request, "The flags were dismissed. The report stays public.")
        return redirect("administration_flagged_reports")

    return render(
        request,
        "reports/flagged_report_review.html",
        {
            "report": report,
            "flags": flags,
            "reason_summary": _reason_summary(flags),
        },
    )


@administrator_required
def remove_flagged_report(request, report_id):
    report, flags = _get_flagged_report(report_id)

    # Solo un POST retira el reporte: abrir la confirmacion no cambia nada.
    if request.method == "POST":
        reviewed_at = timezone.now()
        report.status = ItemReport.Status.REJECTED
        report.moderated_by = request.user
        report.moderated_at = reviewed_at
        with transaction.atomic():
            report.save(update_fields=["status", "moderated_by", "moderated_at", "updated_at"])
            _close_flags(report, request.user, reviewed_at)
            log_action(
                request.user,
                ModerationLogEntry.Action.REMOVED_FROM_PUBLIC,
                report,
                details=_reason_text(flags),
            )
        notify_report_removed(report, [reason for reason, _ in _reason_summary(flags)])

        messages.success(request, f'Report "{report.title}" was removed from public view.')
        return redirect("administration_flagged_reports")

    return render(
        request,
        "reports/flagged_report_confirm_remove.html",
        {"report": report, "reason_summary": _reason_summary(flags)},
    )
