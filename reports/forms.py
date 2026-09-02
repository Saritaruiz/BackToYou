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

        allowed_types = {"image/jpeg", "image/png"}
        content_type = getattr(image, "content_type", "")
        if content_type and content_type not in allowed_types:
            raise forms.ValidationError(
                "Unsupported image format. Allowed formats: JPG, JPEG, PNG."
            )

        max_size = 5 * 1024 * 1024
        if image.size > max_size:
            raise forms.ValidationError("Image exceeds the maximum allowed size of 5 MB.")

        return image


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
