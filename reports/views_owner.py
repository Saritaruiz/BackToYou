"""Views for the actions a user can perform on their own reports (RF11-RF13, RF16)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone

from .decorators import report_owner_required
from .forms import ItemReportForm
from .models import ItemReport


@report_owner_required
def edit_report(request, report):
    # El estado no es un campo del formulario, por eso una edicion nunca lo cambia.
    if not report.is_editable:
        raise PermissionDenied("Rejected reports cannot be edited.")

    if request.method == "POST":
        form = ItemReportForm(
            request.POST,
            request.FILES,
            instance=report,
        )

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Report updated successfully.",
            )

            if report.status == ItemReport.Status.ACTIVE:
                return redirect("reports:report_detail", report_id=report.id)

            return redirect("reports:report_list")

    else:
        form = ItemReportForm(instance=report)

    return render(
        request,
        "reports/report_edit_form.html",
        {
            "form": form,
            "report": report,
        },
    )


@report_owner_required
def delete_report(request, report):
    # Solo un POST borra: abrir la pagina de confirmacion nunca cambia nada.
    if request.method == "POST":
        deleted_title = report.title
        report.delete()

        messages.success(
            request,
            f'Report "{deleted_title}" was deleted.',
        )

        return redirect("reports:report_list")

    return render(
        request,
        "reports/report_confirm_delete.html",
        {"report": report},
    )


@report_owner_required
def mark_report_recovered(request, report):
    # Solo un reporte publicado puede darse por recuperado: los pendientes,
    # rechazados y los ya recuperados quedan fuera.
    if not report.can_be_marked_recovered:
        raise PermissionDenied("Only an active report can be marked as recovered.")

    if request.method == "POST":
        report.status = ItemReport.Status.RECOVERED
        report.recovered_at = timezone.now()

        report.save(
            update_fields=[
                "status",
                "recovered_at",
                "updated_at",
            ],
        )

        messages.success(
            request,
            "The item was marked as recovered.",
        )

        return redirect("reports:report_list")

    return render(
        request,
        "reports/report_confirm_recover.html",
        {"report": report},
    )


@login_required
def my_reports(request):
    reports = (
        ItemReport.objects.filter(creator=request.user)
        .select_related("category")
        # Se desempata por id: en Windows el reloj tiene ~15 ms de
        # granularidad y dos reportes seguidos comparten created_at.
        .order_by("-created_at", "-id")
    )

    return render(
        request,
        "reports/my_reports.html",
        {"reports": reports},
    )
