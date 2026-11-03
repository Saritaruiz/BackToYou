from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

# será para categorizar que tipo de objeto se perdió
class Category(models.Model): 
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

# FR45: periodo de vigencia desde aprobacion o renovacion.
REPORT_VALIDITY = timedelta(days=30)


def default_report_expiration():
    return timezone.now() + REPORT_VALIDITY


# representa cada publicación
class ItemReport(models.Model):
    class ReportType(models.TextChoices):
        LOST = "LOST", _("Lost")
        FOUND = "FOUND", _("Found")


    class Status(models.TextChoices):
        PENDING_REVIEW = "PENDING_REVIEW", _("Pending Review")  # todo reporte nuevo queda automáticamente cómo pendiente
        ACTIVE = "ACTIVE", _("Active")
        RECOVERED = "RECOVERED", _("Recovered")
        REJECTED = "REJECTED", _("Rejected")

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

    # RF10: por que se rechazo o se retiro el reporte. Solo lo ve su creador,
    # para saber que corregir antes de enviarlo de nuevo a revision.
    rejection_reason = models.CharField(max_length=255, blank=True)

    expires_at = models.DateTimeField(default=default_report_expiration)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_expired(self):
        return self.status == self.Status.ACTIVE and self.expires_at <= timezone.now()

    @property
    def is_public(self):
        return self.status == self.Status.ACTIVE and not self.is_expired

    @property
    def can_be_renewed(self):
        return self.status == self.Status.ACTIVE

    @property
    def is_editable(self):
        """RF11: el creador puede editar cualquier reporte suyo.

        Un reporte rechazado se corrige y vuelve a revision (ver edit_report).
        """
        return True

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

    parent_message = models.ForeignKey(
    "self",
    on_delete=models.CASCADE,
    related_name="replies",
    blank=True,
    null=True,
    )

    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message about {self.report}"


# RF43: aviso de un miembro de la comunidad sobre un reporte ya publicado.
class ReportFlag(models.Model):
    class Reason(models.TextChoices):
        FALSE_INFORMATION = "FALSE_INFORMATION", _("False information")
        OFFENSIVE = "OFFENSIVE", _("Offensive content")
        PERSONAL_DATA = "PERSONAL_DATA", _("Personal data")
        OTHER = "OTHER", _("Other")

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
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")
        EDITED = "EDITED", _("Edited")
        REMOVED = "REMOVED", _("Removed")
        FLAGS_DISMISSED = "FLAGS_DISMISSED", _("Flags dismissed")
        REMOVED_FROM_PUBLIC = "REMOVED_FROM_PUBLIC", _("Removed from public view")

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


class ReportReviewNotification(models.Model):
    """FR26: aviso privado, uno por decision del historial de moderacion."""
    class Kind(models.TextChoices):
        APPROVED = "APPROVED", _("Approved")
        REJECTED = "REJECTED", _("Rejected")

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="report_review_notifications",
    )
    report = models.ForeignKey(
        ItemReport, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="review_notifications",
    )
    moderation_entry = models.OneToOneField(
        ModerationLogEntry, on_delete=models.CASCADE,
        related_name="review_notification",
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    # Copia de la decision: sigue legible si se edita o elimina el reporte.
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return self.message
