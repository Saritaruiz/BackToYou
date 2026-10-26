"""Vistas publicas de reportes: listado, busqueda, detalle y contacto.

RF06 Browse Reports - RF07 Search Items - RF08 Contact Reporter
RF18 View Report Details
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from ..email_notifications import notify_report_contact
from ..forms import ContactMessageForm
from ..models import Category, ItemReport
from ..querysets import public_reports, recent_public_reports
from ..statistics import community_numbers


def home(request):
    return render(
        request,
        "home.html",
        {
            "recent_reports": recent_public_reports(),
            # Buscador del inicio: numeros reales y atajos por categoria.
            "numbers": community_numbers(),
            "categories": Category.objects.order_by("name"),
        },
    )


def report_list(request):
    reports = public_reports().select_related("category").order_by("-created_at", "-id")

    query = request.GET.get("q")
    category_id = request.GET.get("category")
    report_type = request.GET.get("type")

    if query:
        reports = reports.filter(
           Q(title__icontains=query)
         | Q(description__icontains=query)
         | Q(location__icontains=query)
         | Q(category__name__icontains=query)
         | Q(report_type__icontains=query)
    )
    if category_id:
        reports = reports.filter(category_id=category_id)

    if report_type:
        reports = reports.filter(report_type=report_type)

    categories = Category.objects.all().order_by("name")
    reports = list(reports)
    return render(
        request,
        "reports/report_list.html",
        {
            "reports": reports,
            # Los reportes con foto se ven como tarjetas; los demas, como
            # filas compactas con el icono de su categoria.
            "reports_with_photo": [report for report in reports if report.image],
            "reports_without_photo": [report for report in reports if not report.image],
            "categories": categories,
            "query": query,
            "selected_category": category_id,
            "selected_type": report_type,
        },
    )


def report_detail(request, report_id):
    report = get_object_or_404(ItemReport, id=report_id)

    is_creator = (
        request.user.is_authenticated
        and request.user == report.creator
    )

    # Un reporte que no esta publicado solo lo puede abrir su creador. Se
    # responde 404 y no 403 para no revelar que el reporte existe.
    if report.status != ItemReport.Status.ACTIVE and not is_creator:
        raise Http404("This report is not available.")

    # Los mensajes recibidos solo los ve el creador del reporte: sin esto,
    # RF08 guarda el mensaje pero el destinatario no tiene donde leerlo.
    contact_messages = (
        report.contact_messages.select_related("sender").order_by("-created_at", "-id")
        if is_creator
        else []
    )

    # RF43: quien ya aviso sobre el reporte lo ve, pero nadie mas sabe quien fue.
    can_be_flagged = (
        request.user.is_authenticated
        and not is_creator
        and report.status == ItemReport.Status.ACTIVE
    )
    has_flagged_report = can_be_flagged and report.flags.filter(flagged_by=request.user).exists()

    return render(
        request,
        "reports/report_detail.html",
        {
            "report": report,
            "is_creator": is_creator,
            "contact_messages": contact_messages,
            "can_contact_reporter": (
                request.user.is_authenticated
                and not is_creator
                and report.status == ItemReport.Status.ACTIVE
            ),
            "can_edit_report": is_creator and report.is_editable,
            "can_delete_report": is_creator,
            "can_mark_recovered": is_creator and report.can_be_marked_recovered,
            "can_flag_report": can_be_flagged and not has_flagged_report,
            "has_flagged_report": has_flagged_report,
        },
    )


@login_required
def contact_reporter(request, report_id):
    report = get_object_or_404(
        ItemReport,
        id=report_id,
        status=ItemReport.Status.ACTIVE,
    )

    if report.creator == request.user:
        raise PermissionDenied("You cannot contact yourself about your own report.")

    if request.method == "POST":
        form = ContactMessageForm(request.POST)
        if form.is_valid():
            contact_message = form.save(commit=False)
            contact_message.report = report
            contact_message.sender = request.user
            contact_message.save()
            notify_report_contact(contact_message)

            messages.success(
                request,
                "Your message was sent to the reporter inside BackToYou.",
            )
            return redirect("reports:report_detail", report_id=report.id)
    else:
        form = ContactMessageForm()

    return render(
        request,
        "reports/contact_reporter.html",
        {
            "form": form,
            "report": report,
        },
    )
