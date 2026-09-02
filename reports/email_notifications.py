import logging

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


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
        "BackToYou - New message about your report",
        (
            "Someone contacted you about your BackToYou report.\n\n"
            f"Report: {report.title}\n\n"
            f"Message:\n{contact_message.message}\n\n"
            "Log into BackToYou to view the report context."
        ),
    )


def notify_report_approved(report):
    return _send_notification(
        report.creator.email,
        "BackToYou - Your report was approved",
        (
            "Your BackToYou report was approved.\n\n"
            f"Report: {report.title}\n"
            "Status: ACTIVE\n\n"
            "Your report is now publicly visible in BackToYou."
        ),
    )


def notify_report_rejected(report):
    return _send_notification(
        report.creator.email,
        "BackToYou - Your report was rejected",
        (
            "Your BackToYou report was reviewed and rejected.\n\n"
            f"Report: {report.title}\n"
            "Status: REJECTED\n\n"
            "This report will not appear in the public report list."
        ),
    )
