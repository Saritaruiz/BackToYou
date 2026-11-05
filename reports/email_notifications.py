import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import gettext as _


logger = logging.getLogger(__name__)

# Los correos salen en el idioma de la pagina de quien hace la accion (el
# administrador que aprueba, la persona que escribe): la app no guarda el
# idioma de cada cuenta.


def _send_notification(recipient_email, subject, message):
    if not recipient_email:
        return False

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("BackToYou email notification failed.")
        return False

    return True


def notify_report_contact(contact_message):
    report = contact_message.report
    return _send_notification(
        report.creator.email,
        _("BackToYou - New message about your report"),
        _(
            "Someone contacted you about your BackToYou report.\n\n"
            "Report: %(title)s\n\n"
            "Message:\n%(message)s\n\n"
            "Log in to BackToYou to view the report context."
        ) % {"title": report.title, "message": contact_message.message},
    )


def notify_report_approved(report):
    return _send_notification(
        report.creator.email,
        _("BackToYou - Your report was approved"),
        _(
            "Your BackToYou report was approved.\n\n"
            "Report: %(title)s\n"
            "Status: ACTIVE\n\n"
            "Your report is now publicly visible in BackToYou."
        ) % {"title": report.title},
    )


def notify_report_rejected(report):
    return _send_notification(
        report.creator.email,
        _("BackToYou - Your report was rejected"),
        _(
            "Your BackToYou report was reviewed and rejected.\n\n"
            "Report: %(title)s\n"
            "Reason: %(reason)s\n"
            "Status: REJECTED\n\n"
            "This report will not appear in the public report list. You can "
            "fix it from My Reports and send it for review again."
        ) % {"title": report.title, "reason": report.rejection_reason or _("Not specified")},
    )


def notify_report_removed(report, reasons):
    """RF43: el creador sabe por que se retiro su reporte, pero no quien aviso."""
    return _send_notification(
        report.creator.email,
        _("BackToYou - Your report was removed from public view"),
        _(
            "Members of the community flagged your BackToYou report. An "
            "administrator reviewed it and removed it from public view.\n\n"
            "Report: %(title)s\n"
            "Reason: %(reasons)s\n"
            "Status: REJECTED\n\n"
            "If the item is still lost or found, you can create a new report "
            "without the problem."
        ) % {"title": report.title, "reasons": ", ".join(str(reason) for reason in reasons)},
    )
