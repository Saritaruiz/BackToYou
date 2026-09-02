from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.decorators import administrator_required
from .email_notifications import (
    notify_report_approved,
    notify_report_contact,
    notify_report_rejected,
)
from .forms import CategoryForm, ContactMessageForm, ItemReportForm
from .models import Category, ItemReport


def report_list(request):
    reports = ItemReport.objects.filter(
        status=ItemReport.Status.ACTIVE
    ).order_by("-created_at", "-id")

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
    return render(
        request,
        "reports/report_list.html",
        {
            "reports": reports,
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

    return render(
        request,
        "reports/report_detail.html",
        {
            "report": report,
            "is_creator": is_creator,
            "can_contact_reporter": (
                request.user.is_authenticated
                and not is_creator
                and report.status == ItemReport.Status.ACTIVE
            ),
            "can_edit_report": is_creator and report.is_editable,
            "can_delete_report": is_creator,
            "can_mark_recovered": is_creator and report.can_be_marked_recovered,
        },
    )


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
                "Report submitted successfully. It is currently Pending Review and will become publicly visible after administrator approval.",
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
        elif action == "reject":
            report.status = ItemReport.Status.REJECTED
            success_message = "Report rejected successfully."
            notify_moderation_result = notify_report_rejected
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
        notify_moderation_result(report)

        messages.success(request, success_message)
        return redirect("administration_pending_reports")

    return render(
        request,
        "reports/moderation_report_detail.html",
        {"report": report},
    )


@administrator_required
def category_list(request):
    categories = Category.objects.all().order_by("name")

    return render(
        request,
        "reports/category_list.html",
        {"categories": categories},
    )


@administrator_required
def category_create(request):
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Category created successfully.")
            return redirect("administration_category_list")
    else:
        form = CategoryForm()

    return render(
        request,
        "reports/category_form.html",
        {
            "form": form,
            "title": "Create Category",
            "submit_label": "Create Category",
        },
    )


@administrator_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, "Category updated successfully.")
            return redirect("administration_category_list")
    else:
        form = CategoryForm(instance=category)

    return render(
        request,
        "reports/category_form.html",
        {
            "form": form,
            "category": category,
            "title": "Edit Category",
            "submit_label": "Save Changes",
        },
    )


@administrator_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)

    if request.method == "POST":
        try:
            category.delete()
        except ProtectedError:
            messages.error(
                request,
                "This category cannot be deleted because it is currently used by one or more reports.",
            )
            return redirect("administration_category_list")

        messages.success(request, "Category deleted successfully.")
        return redirect("administration_category_list")

    return render(
        request,
        "reports/category_confirm_delete.html",
        {"category": category},
    )
