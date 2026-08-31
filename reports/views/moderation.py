"""Moderacion de reportes por parte de un administrador.

RF10 Moderate Reports
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import administrator_required

from ..models import ItemReport


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
        elif action == "reject":
            report.status = ItemReport.Status.REJECTED
            success_message = "Report rejected successfully."
        else:
            raise PermissionDenied("Invalid moderation action.")

        report.moderated_by = request.user
        report.moderated_at = timezone.now()
        report.save(
            update_fields=[
                "status",
                "moderated_by",
                "moderated_at",
                "updated_at",
            ],
        )

        messages.success(request, success_message)
        return redirect("administration_pending_reports")

    return render(
        request,
        "reports/moderation_report_detail.html",
        {"report": report},
    )
