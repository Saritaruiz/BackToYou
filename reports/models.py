from django.conf import settings
from django.db import models

# será para categorizar que tipo de objeto se perdió
class Category(models.Model): 
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# representa cada publicación
class ItemReport(models.Model):
    class ReportType(models.TextChoices):
        LOST = "LOST", "Lost"
        FOUND = "FOUND", "Found"


    class Status(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", "Pending Review"  # todo reporte nuevo queda automáticamente cómo pendiente
        ACTIVE = "ACTIVE", "Active"
        RECOVERED = "RECOVERED", "Recovered"
        REJECTED = "REJECTED", "Rejected"

    title = models.CharField(max_length=150)
    description = models.TextField()

    report_type = models.CharField(
        max_length=10,
        choices=ReportType.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_REVIEW,
    )

    event_date = models.DateField()
    location = models.CharField(max_length=200)

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="reports",
    )

    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="item_reports",
    )

    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="moderated_item_reports",
        blank=True,
        null=True,
    )

    moderated_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    # Momento en que el creador marco el objeto como recuperado (RF13).
    # Es la fecha desde la que se cuenta la retencion definida en DR05.
    recovered_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    image = models.ImageField(
        upload_to="reports/",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_editable(self):
        """RF11: el creador puede editar todo menos un reporte rechazado."""
        return self.status != self.Status.REJECTED

    @property
    def can_be_marked_recovered(self):
        """RF13: solo un reporte publicado puede darse por recuperado."""
        return self.status == self.Status.ACTIVE


class ContactMessage(models.Model):
    report = models.ForeignKey(
        ItemReport,
        on_delete=models.CASCADE,
        related_name="contact_messages",
    )

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_contact_messages",
    )

    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message about {self.report}"
