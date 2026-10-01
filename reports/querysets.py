"""Shared public visibility and RF24 publication ordering."""
from django.db.models.functions import Coalesce

from .models import ItemReport


def public_reports():
    return ItemReport.objects.filter(status=ItemReport.Status.ACTIVE)


def recent_public_reports():
    return (
        public_reports()
        .select_related("category")
        .annotate(published_at=Coalesce("moderated_at", "created_at"))
        .order_by("-published_at", "-id")[:6]
    )
