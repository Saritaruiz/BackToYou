from django import forms

from .models import Category, ContactMessage, ItemReport


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


class ItemReportForm(forms.ModelForm):
    class Meta:
        model = ItemReport
        fields = ("title", "description", "category", "event_date", "location", "image")
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

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

    def __init__(self, data=None, *args, **kwargs):
        if data is not None and "description_method" not in data:
            data = data.copy()
            data["description_method"] = "manual"
        super().__init__(data, *args, **kwargs)
        self.order_fields(["description_method", *ItemReportForm.Meta.fields])


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
