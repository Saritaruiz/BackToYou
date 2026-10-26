"""RF44 Moderation Activity Log: historial de solo lectura para administradores."""

from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.decorators import administrator_required

from ..models import ModerationLogEntry


ENTRIES_PER_PAGE = 50


@administrator_required
def activity_log(request):
    entries = ModerationLogEntry.objects.select_related("report").order_by("-created_at", "-id")

    selected_administrator = request.GET.get("administrator", "")
    selected_action = request.GET.get("action", "")

    if selected_administrator.isdigit():
        entries = entries.filter(administrator_id=selected_administrator)
    else:
        selected_administrator = ""

    if selected_action in ModerationLogEntry.Action.values:
        entries = entries.filter(action=selected_action)
    else:
        selected_action = ""

    # Solo se ofrecen los administradores que tienen acciones en el historial.
    administrators = (
        get_user_model()
        .objects.filter(moderation_log_entries__isnull=False)
        .distinct()
        .order_by("email")
    )

    page = Paginator(entries, ENTRIES_PER_PAGE).get_page(request.GET.get("page"))

    return render(
        request,
        "reports/activity_log.html",
        {
            "page": page,
            "administrators": administrators,
            "actions": ModerationLogEntry.Action.choices,
            "selected_administrator": selected_administrator,
            "selected_action": selected_action,
        },
    )
