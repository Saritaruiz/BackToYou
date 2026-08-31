"""Creacion de reportes.

RF03 Create Lost Item Report - RF04 Create Found Item Report
RF05 Upload Item Image - RF17 Report Submission Confirmation
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ..forms import ItemReportForm
from ..models import ItemReport


@login_required
def create_lost_report(request):
    return _create_report(
        request,
        ItemReport.ReportType.LOST,
    )


@login_required
def create_found_report(request):
    return _create_report(
        request,
        ItemReport.ReportType.FOUND,
    )


def _create_report(request, report_type):
    if request.method == "POST":
        form = ItemReportForm(
            request.POST,
            request.FILES,
        )

        if form.is_valid():
            report = form.save(commit=False)

            report.creator = request.user
            report.report_type = report_type
            report.status = ItemReport.Status.PENDING_REVIEW

            report.save()

            messages.success(
                request,
                "Report submitted for administrator review.",
            )

            return redirect(
                "reports:report_list"
            )

    else:
        form = ItemReportForm()

    report_type_label = (
        "Lost"
        if report_type == ItemReport.ReportType.LOST
        else "Found"
    )

    return render(
        request,
        "reports/report_form.html",
        {
            "form": form,
            "report_type_label": report_type_label,
        },
    )
