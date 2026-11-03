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
from django.utils.translation import gettext as _

from ..email_notifications import notify_report_contact
from ..forms import ContactMessageForm
from ..models import Category, ContactMessage, ItemReport
from ..querysets import public_reports
from ..search import Normalized, normalize
from ..statistics import community_numbers


def home(request):
    # Los reportes no van en el inicio: se ven en el indice (report_list).
    return render(
        request,
        "home.html",
        {
            # Buscador del inicio: numeros reales y atajos por categoria.
            "numbers": community_numbers(),
            "categories": Category.objects.order_by("name"),
        },
    )


def report_list(request):
    reports = public_reports().select_related("category")

    query = request.GET.get("q", "").strip()
    category_id = request.GET.get("category", "").strip()
    report_type = request.GET.get("type", "").strip()
    location = request.GET.get("location", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    sort = request.GET.get("sort", "newest").strip()

    if query:
        # RF07: "camara" encuentra "Cámara" y "CÁMARA" (ver search.py).
        text = normalize(query)

        # i18n: el nombre de la categoria tambien se busca como se ve en la
        # pagina, asi "llaves" encuentra la categoria "Keys" en espanol.
        translated_categories = [
            category.id
            for category in Category.objects.all()
            if text in normalize(_(category.name))
        ]

        reports = reports.annotate(
            search_title=Normalized("title"),
            search_description=Normalized("description"),
            search_location=Normalized("location"),
            search_category=Normalized("category__name"),
        ).filter(
            Q(search_title__contains=text)
            | Q(search_description__contains=text)
            | Q(search_location__contains=text)
            | Q(search_category__contains=text)
            | Q(category_id__in=translated_categories)
            | Q(report_type__icontains=query)
        )

    if category_id:
        reports = reports.filter(category_id=category_id)

    if report_type in ItemReport.ReportType.values:
        reports = reports.filter(report_type=report_type)

    # FR42: advanced location filter.
    if location:
        reports = reports.annotate(
            filter_location=Normalized("location"),
        ).filter(
            filter_location__contains=normalize(location)
        )

    # FR42: event date range.
    if date_from:
        reports = reports.filter(event_date__gte=date_from)

    if date_to:
        reports = reports.filter(event_date__lte=date_to)

    # FR42: explicit sorting options.
    sorting_options = {
        "newest": ("-created_at", "-id"),
        "oldest": ("created_at", "id"),
        "event_newest": ("-event_date", "-id"),
        "event_oldest": ("event_date", "id"),
        "title_asc": ("title", "id"),
        "title_desc": ("-title", "-id"),
    }

    reports = reports.order_by(
        *sorting_options.get(sort, sorting_options["newest"])
    )

    categories = Category.objects.all().order_by("name")
    reports = list(reports)

    return render(
        request,
        "reports/report_list.html",
        {
            "reports": reports,
            # Los reportes con foto se ven como tarjetas; los demas, como
            # filas compactas con el icono de su categoria.
            "reports_with_photo": [
                report for report in reports if report.image
            ],
            "reports_without_photo": [
                report for report in reports if not report.image
            ],
            "categories": categories,
            "query": query,
            "selected_category": category_id,
            "selected_type": report_type,
            "selected_location": location,
            "selected_date_from": date_from,
            "selected_date_to": date_to,
            "selected_sort": sort,
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
# FR40: el creador ve los mensajes recibidos y sus respuestas.
# El usuario que contacto al creador puede ver sus propios mensajes
# y las respuestas que recibió dentro de BackToYou.
    if is_creator:
        contact_messages = (
        report.contact_messages
        .filter(parent_message__isnull=True)
        .select_related("sender")
        .prefetch_related("replies__sender")
        .order_by("-created_at", "-id")
    )
    elif request.user.is_authenticated:
         contact_messages = (
        report.contact_messages
        .filter(
            parent_message__isnull=True,
            sender=request.user,
        )
        .select_related("sender")
        .prefetch_related("replies__sender")
        .order_by("-created_at", "-id")
    )
    else:
       contact_messages = []

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
                _("Your message was sent to the reporter inside BackToYou."),
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

@login_required
def reply_to_contact_message(request, message_id):
    # FR40: solo el creador del reporte puede responder un mensaje recibido.
    original_message = get_object_or_404(
        ContactMessage.objects.select_related("report", "sender"),
        id=message_id,
        parent_message__isnull=True,
    )

    report = original_message.report

    if report.creator != request.user:
        raise PermissionDenied(
            "Only the report creator can reply to this message."
        )

    if request.method == "POST":
        form = ContactMessageForm(request.POST)

        if form.is_valid():
            reply = form.save(commit=False)
            reply.report = report
            reply.sender = request.user
            reply.parent_message = original_message
            reply.save()

            messages.success(
                request,
                _("Your reply was sent inside BackToYou."),
            )

            return redirect(
                "reports:report_detail",
                report_id=report.id,
            )
    else:
        form = ContactMessageForm()

    return render(
        request,
        "reports/reply_contact_message.html",
        {
            "form": form,
            "report": report,
            "original_message": original_message,
        },
    )
