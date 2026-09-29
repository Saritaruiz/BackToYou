"""RF22 - AI-Based Object Description.

El formulario de creacion llama a esta vista con la foto y recibe una
sugerencia en JSON para llenar los campos. No crea ni modifica reportes.
"""

from django import forms
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .. import ai_description
from ..forms import validate_report_image
from ..models import Category, ItemReport


@login_required
@require_POST
def describe_item(request):
    if not ai_description.is_available():
        return JsonResponse(
            {"error": "AI suggestions are not available right now. Please fill in the report manually."},
            status=503,
        )

    image = request.FILES.get("image")
    if not image:
        return JsonResponse(
            {"error": "Upload a photo of the item to get an AI suggestion."},
            status=400,
        )

    try:
        validate_report_image(image)
    except forms.ValidationError as error:
        return JsonResponse({"error": error.messages[0]}, status=400)

    report_type = request.POST.get("report_type")
    report_type_label = (
        ItemReport.ReportType(report_type).label
        if report_type in ItemReport.ReportType.values
        else "Lost or found"
    )

    categories = {category.name: category.id for category in Category.objects.order_by("name")}

    try:
        suggestion = ai_description.describe_item_image(
            image,
            report_type_label,
            list(categories),
        )
    except ai_description.AIDescriptionError as error:
        return JsonResponse({"error": str(error)}, status=502)

    return JsonResponse(
        {
            "title": suggestion["title"],
            "description": suggestion["description"],
            "category_id": categories.get(suggestion["category"]),
        }
    )
