from django.conf import settings
from django.core.exceptions import PermissionDenied
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


# RF43: aviso de un miembro de la comunidad sobre un reporte ya publicado.
class ReportFlag(models.Model):
    class Reason(models.TextChoices):
        FALSE_INFORMATION = "FALSE_INFORMATION", "False information"
        OFFENSIVE = "OFFENSIVE", "Offensive content"
        PERSONAL_DATA = "PERSONAL_DATA", "Personal data"
        OTHER = "OTHER", "Other"

    report = models.ForeignKey(
        ItemReport,
        on_delete=models.CASCADE,
        related_name="flags",
    )

    flagged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="report_flags",
    )

    reason = models.CharField(max_length=20, choices=Reason.choices)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Administrador que reviso el aviso, al descartarlo o al retirar el
    # reporte. Mientras esta vacio, el aviso sigue abierto.
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_report_flags",
        blank=True,
        null=True,
    )

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        constraints = [
            # Cada persona avisa una sola vez sobre el mismo reporte.
            models.UniqueConstraint(
                fields=["report", "flagged_by"],
                name="unique_flag_per_user_and_report",
            ),
        ]

    def __str__(self):
        return f"{self.get_reason_display()} flag on {self.report}"


# RF44: historial de moderacion. Completa DR06, que en el reporte solo
# guarda la ultima decision.
class ModerationLogEntry(models.Model):
    class Action(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        EDITED = "EDITED", "Edited"
        REMOVED = "REMOVED", "Removed"
        FLAGS_DISMISSED = "FLAGS_DISMISSED", "Flags dismissed"
        REMOVED_FROM_PUBLIC = "REMOVED_FROM_PUBLIC", "Removed from public view"

    action = models.CharField(max_length=30, choices=Action.choices)

    administrator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="moderation_log_entries",
        blank=True,
        null=True,
    )

    # Copias del momento de la accion: la entrada sigue legible aunque el
    # reporte se elimine o la cuenta del administrador cambie.
    administrator_email = models.EmailField()

    report = models.ForeignKey(
        ItemReport,
        on_delete=models.SET_NULL,
        related_name="moderation_log_entries",
        blank=True,
        null=True,
    )

    report_title = models.CharField(max_length=150)
    details = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.get_action_display()}: {self.report_title}"

    # Una entrada del historial no se cambia ni se borra desde la aplicacion.
    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied("Moderation log entries cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Moderation log entries cannot be deleted.")
