"""Views for the actions a user can perform on their own reports (RF11-RF13, RF16)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.views.decorators.http import require_http_methods
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from ..decorators import report_owner_required
from ..forms import OLD_EVENT_DATE_WARNING, ItemReportForm, event_date_is_old
from ..models import ItemReport, REPORT_VALIDITY


@report_owner_required
def edit_report(request, report):
    # El estado no es un campo del formulario: una edicion solo lo cambia
    # cuando el reporte estaba rechazado (ver abajo).
    if not report.is_editable:
        raise PermissionDenied("This report cannot be edited.")

    if request.method == "POST":
        form = ItemReportForm(
            request.POST,
            request.FILES,
            instance=report,
        )

        if form.is_valid():
            report = form.save(commit=False)

            # RF10: corregir un reporte rechazado lo envia de nuevo a revision.
            if report.status == ItemReport.Status.REJECTED:
                report.status = ItemReport.Status.PENDING_REVIEW
                report.rejection_reason = ""
                report.save()
                messages.success(
                    request,
                    _("Report updated and sent for review again. An administrator will check it before it becomes public."),
                )
            else:
                report.save()
                messages.success(
                    request,
                    _("Report updated successfully."),
                )
            if "event_date" in form.changed_data and event_date_is_old(report.event_date):
                messages.warning(request, OLD_EVENT_DATE_WARNING)

            if report.status == ItemReport.Status.ACTIVE:
                return redirect("reports:report_detail", report_id=report.id)

            # RF17: igual que al crear, la fila del reporte queda resaltada.
            return redirect(f"{reverse('reports:my_reports')}#report-{report.id}")

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
            _('Report "%(title)s" was deleted.') % {"title": deleted_title},
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

        # NFR36: "recovered" activa la celebracion discreta del aviso.
        messages.success(
            request,
            _("The item was marked as recovered. It is back with its owner."),
            extra_tags="recovered",
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


@report_owner_required
@require_http_methods(["GET", "POST"])
def renew_report(request, report):
    """FR45: renovar no cambia contenido, moderacion ni fechas historicas."""
    if not report.can_be_renewed:
        raise PermissionDenied("Only an active report can be renewed.")
    if request.method == "POST":
        now = timezone.now()
        # Una sola actualizacion condicional: no reactiva un reporte retirado
        # mientras se confirmaba ni pierde extensiones concurrentes.
        updated = ItemReport.objects.filter(
            pk=report.pk, creator=request.user, status=ItemReport.Status.ACTIVE,
        ).update(
            expires_at=Greatest(F("expires_at"), Value(now)) + REPORT_VALIDITY,
            updated_at=now,
        )
        if not updated:
            raise PermissionDenied("Only an active report can be renewed.")
        messages.success(request, _("Report renewed for 30 more days."))
        return redirect("reports:report_detail", report_id=report.pk)
    return render(request, "reports/report_confirm_renew.html", {
        "report": report,
        "renewed_until": max(report.expires_at, timezone.now()) + REPORT_VALIDITY,
    })
