"""Moderacion de reportes por parte de un administrador.

RF10 Moderate Reports
RF21 Administrator Role Management: ademas de aprobar o rechazar, un
administrador puede editar o eliminar un reporte mientras sigue pendiente
de revision, es decir, antes de que sea visible para el publico.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import administrator_required

from ..email_notifications import notify_report_approved, notify_report_rejected
from ..forms import ItemReportForm
from ..models import ItemReport, ModerationLogEntry
from ..moderation_log import log_action


@administrator_required
def pending_report_list(request):
    reports = ItemReport.objects.filter(
        status=ItemReport.Status.PENDING_REVIEW,
    ).order_by("-created_at", "-id")

    return render(
        request,
        "reports/moderation_pending_list.html",
        {"reports": reports},
    )


@administrator_required
def moderate_report_detail(request, report_id):
    report = get_object_or_404(
        ItemReport,
        id=report_id,
        status=ItemReport.Status.PENDING_REVIEW,
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            report.status = ItemReport.Status.ACTIVE
            success_message = "Report approved successfully."
            notify_moderation_result = notify_report_approved
            log_entry_action = ModerationLogEntry.Action.APPROVED
        elif action == "reject":
            report.status = ItemReport.Status.REJECTED
            success_message = "Report rejected successfully."
            notify_moderation_result = notify_report_rejected
            log_entry_action = ModerationLogEntry.Action.REJECTED
        else:
            raise PermissionDenied("Invalid moderation action.")

        report.moderated_by = request.user
        report.moderated_at = timezone.now()
        with transaction.atomic():
            report.save(
                update_fields=[
                    "status",
                    "moderated_by",
                    "moderated_at",
                    "updated_at",
                ],
            )
            log_action(request.user, log_entry_action, report)
        notify_moderation_result(report)

        messages.success(request, success_message)
        return redirect("administration_pending_reports")

    return render(
        request,
        "reports/moderation_report_detail.html",
        {"report": report},
    )


@administrator_required
def edit_pending_report(request, report_id):
    report = get_object_or_404(
        ItemReport,
        id=report_id,
        status=ItemReport.Status.PENDING_REVIEW,
    )

    if request.method == "POST":
        form = ItemReportForm(request.POST, request.FILES, instance=report)

        if form.is_valid():
            with transaction.atomic():
                form.save()
                # Guardar sin cambios no deja entrada en el historial.
                if form.has_changed():
                    changed = ", ".join(str(form.fields[name].label) for name in form.changed_data)
                    log_action(
                        request.user,
                        ModerationLogEntry.Action.EDITED,
                        report,
                        details=f"Changed: {changed}",
                    )

            messages.success(request, "Report updated successfully.")
            return redirect("administration_moderate_report", report_id=report.id)
    else:
        form = ItemReportForm(instance=report)

    return render(
        request,
        "reports/moderation_report_edit.html",
        {"form": form, "report": report},
    )


@administrator_required
def delete_pending_report(request, report_id):
    report = get_object_or_404(
        ItemReport,
        id=report_id,
        status=ItemReport.Status.PENDING_REVIEW,
    )

    if request.method == "POST":
        deleted_title = report.title
        with transaction.atomic():
            log_action(request.user, ModerationLogEntry.Action.REMOVED, report)
            report.delete()

        messages.success(request, f'Report "{deleted_title}" was removed.')
        return redirect("administration_pending_reports")

    return render(
        request,
        "reports/moderation_report_confirm_delete.html",
        {"report": report},
    )
