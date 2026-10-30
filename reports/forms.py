from datetime import timedelta

from django import forms
from django.utils import timezone

from .models import Category, ContactMessage, ItemReport, ReportFlag


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name",)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Category name cannot be empty.")

        duplicate = Category.objects.filter(name__iexact=name)
        if self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)

        if duplicate.exists():
            raise forms.ValidationError("A category with this name already exists.")

        return name


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


def validate_report_image(image):
    """RF05: reglas de la imagen del reporte. Tambien las usa RF22."""
    content_type = getattr(image, "content_type", "")
    if content_type and content_type not in ALLOWED_IMAGE_TYPES:
        raise forms.ValidationError(
            "Unsupported image format. Allowed formats: JPG, JPEG, PNG."
        )

    if image.size > MAX_IMAGE_SIZE:
        raise forms.ValidationError("Image exceeds the maximum allowed size of 5 MB.")


# RF03/RF04: una fecha de hace mas de un ano casi siempre es un error al
# escribirla. No se bloquea, pero se avisa despues de guardar.
EVENT_DATE_WARNING_DAYS = 365
OLD_EVENT_DATE_WARNING = (
    "The date of this report is more than a year ago. If that is a mistake, "
    "edit the report to fix it."
)


def event_date_is_old(event_date):
    return event_date < timezone.localdate() - timedelta(days=EVENT_DATE_WARNING_DAYS)


class ItemReportForm(forms.ModelForm):
    class Meta:
        model = ItemReport
        fields = ("title", "description", "category", "event_date", "location", "image")
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # RF03/RF04: el calendario del navegador no deja elegir fechas futuras.
        self.fields["event_date"].widget.attrs["max"] = timezone.localdate().isoformat()

    def clean_event_date(self):
        # Un objeto no se pierde ni se encuentra en el futuro.
        event_date = self.cleaned_data["event_date"]
        if event_date > timezone.localdate():
            raise forms.ValidationError("The date cannot be in the future.")
        return event_date

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image

        validate_report_image(image)
        return image


class ItemReportCreationForm(ItemReportForm):
    """RF23: a preparation choice, never persisted on the report."""

    description_method = forms.ChoiceField(
        label="Description method",
        choices=(("manual", "Manual"), ("ai", "AI-assisted")),
        initial="manual",
        widget=forms.RadioSelect,
    )

    def __init__(self, data=None, *args, report_type=ItemReport.ReportType.LOST, **kwargs):
        if data is not None and "description_method" not in data:
            data = data.copy()
            data["description_method"] = "manual"
        super().__init__(data, *args, **kwargs)
        self.order_fields(["description_method", *ItemReportForm.Meta.fields])

        # Quien encontro el objeto lo tiene en la mano: la foto es obligatoria
        # y ayuda al dueno a reconocerlo. Para Lost sigue siendo opcional.
        image = self.fields["image"]
        if report_type == ItemReport.ReportType.FOUND:
            image.required = True
            image.error_messages["required"] = "Add a photo of the item you found so its owner can recognize it."
            image.help_text = "Required: you have the item with you, so a photo helps its owner recognize it."
        else:
            image.help_text = "Optional: add one if you have a photo of the item."


# RF10: motivos de rechazo. El texto es el que lee el creador del reporte.
REJECTION_REASONS = {
    "unclear": "The description or the photo is not clear enough to recognize the item.",
    "personal_data": "The report shows personal data, such as names, ID numbers or phone numbers.",
    "duplicate": "There is already a report for this item.",
    "not_an_item": "The report is not about a lost or found item.",
    "inappropriate": "The report has inappropriate content.",
}


class RejectionForm(forms.Form):
    """RF10: el administrador explica el rechazo para que el creador pueda corregirlo."""

    # Va en el mismo formulario que "Approve": el navegador no debe exigir
    # el motivo para aprobar. Solo se valida al rechazar.
    use_required_attribute = False

    reason = forms.ChoiceField(
        label="Reason to show the reporter if you reject",
        choices=[("", "Choose a reason"), *REJECTION_REASONS.items()],
        error_messages={"required": "Choose a reason before rejecting, so the reporter knows what to fix."},
    )
    note = forms.CharField(
        label="Note for the reporter (optional)",
        required=False,
        max_length=120,
    )

    def rejection_text(self):
        reason = REJECTION_REASONS[self.cleaned_data["reason"]]
        return f"{reason} {self.cleaned_data['note'].strip()}".strip()


class ContactMessageForm(forms.ModelForm):
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 5}),
    )

    class Meta:
        model = ContactMessage
        fields = ("message",)

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if not message:
            raise forms.ValidationError("Message cannot be empty.")
        return message


class ReportFlagForm(forms.ModelForm):
    """RF43: el motivo es obligatorio; los detalles ayudan al administrador."""

    reason = forms.ChoiceField(
        choices=ReportFlag.Reason.choices,
        widget=forms.RadioSelect,
        error_messages={"required": "Choose a reason for flagging this report."},
    )
    details = forms.CharField(
        label="Details (optional)",
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="What is wrong with the report? Do not include personal data.",
    )

    class Meta:
        model = ReportFlag
        fields = ("reason", "details")

    def clean_details(self):
        return self.cleaned_data["details"].strip()
