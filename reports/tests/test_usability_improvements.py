"""Mejoras de usabilidad sobre requisitos que ya existian.

- RF07: la busqueda ignora tildes y mayusculas.
- RF03/RF04: la fecha del evento no puede ser futura; si tiene mas de un
  ano, se avisa.
- RF17: despues de crear un reporte, la app lleva a "My Reports" con ese
  reporte resaltado.
- RF08: quien no inicio sesion puede llegar a contactar, y los dos lados
  saben por donde sigue la conversacion.
- RF10: el rechazo lleva un motivo que el creador ve y puede corregir.
"""

import re
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from ..models import Category, ContactMessage, ItemReport, ModerationLogEntry, ReportFlag


PASSWORD = "StrongPass123"


class ReportTestCase(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user("creator@eafit.edu.co", "creator@eafit.edu.co", PASSWORD)
        self.other = User.objects.create_user("other@eafit.edu.co", "other@eafit.edu.co", PASSWORD)
        self.admin = User.objects.create_user(
            "admin@eafit.edu.co", "admin@eafit.edu.co", PASSWORD, role=User.Role.ADMINISTRATOR
        )
        self.category = Category.objects.create(name="Electronics")

    def create_report(self, title="Lost calculator", status=ItemReport.Status.ACTIVE, **fields):
        return ItemReport.objects.create(
            title=title,
            description=fields.pop("description", "Black scientific calculator"),
            report_type=fields.pop("report_type", ItemReport.ReportType.LOST),
            status=status,
            event_date=fields.pop("event_date", timezone.localdate()),
            location=fields.pop("location", "Library"),
            category=self.category,
            creator=fields.pop("creator", self.creator),
            **fields,
        )

    def login_as(self, user):
        self.client.force_login(user)

    def report_payload(self, **changes):
        return {
            "title": "Lost keys",
            "description": "Three keys on a blue keyring",
            "category": self.category.id,
            "event_date": timezone.localdate().isoformat(),
            "location": "Block 19",
            **changes,
        }


class AccentInsensitiveSearchTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.canon = self.create_report("Cámara Canon")
        self.sony = self.create_report("CÁMARA SONY")
        self.pending = self.create_report("Cámara Nikon", status=ItemReport.Status.PENDING_REVIEW)
        self.cafeteria = self.create_report("Blue umbrella", location="Cafetería central")

    def titles_found(self, query):
        response = self.client.get(reverse("reports:report_list"), {"q": query})
        return {report.title for report in response.context["reports"]}

    def test_a_search_without_accents_finds_words_with_accents(self):
        self.assertEqual(self.titles_found("camara"), {"Cámara Canon", "CÁMARA SONY"})

    def test_case_is_ignored_even_on_letters_with_accents(self):
        self.assertEqual(self.titles_found("cámara"), {"Cámara Canon", "CÁMARA SONY"})
        self.assertEqual(self.titles_found("CAMARA"), {"Cámara Canon", "CÁMARA SONY"})

    def test_the_location_is_searched_the_same_way(self):
        self.assertEqual(self.titles_found("cafeteria"), {"Blue umbrella"})

    def test_a_specific_word_still_narrows_the_results(self):
        self.assertEqual(self.titles_found("canon"), {"Cámara Canon"})

    def test_pending_reports_stay_out_of_the_results(self):
        self.assertNotIn("Cámara Nikon", self.titles_found("nikon"))


class EventDateTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.login_as(self.creator)

    def test_a_future_date_is_rejected(self):
        tomorrow = timezone.localdate() + timedelta(days=1)

        response = self.client.post(
            reverse("reports:create_lost_report"),
            self.report_payload(event_date=tomorrow.isoformat()),
        )

        self.assertContains(response, "The date cannot be in the future.")
        self.assertFalse(ItemReport.objects.exists())

    def test_the_calendar_does_not_offer_future_dates(self):
        response = self.client.get(reverse("reports:create_lost_report"))

        self.assertContains(response, f'max="{timezone.localdate().isoformat()}"')

    def test_a_date_older_than_a_year_is_saved_with_a_warning(self):
        old = timezone.localdate() - timedelta(days=400)

        response = self.client.post(
            reverse("reports:create_lost_report"),
            self.report_payload(event_date=old.isoformat()),
            follow=True,
        )

        self.assertTrue(ItemReport.objects.filter(event_date=old).exists())
        self.assertContains(response, "more than a year ago")

    def test_a_recent_date_has_no_warning(self):
        response = self.client.post(
            reverse("reports:create_lost_report"), self.report_payload(), follow=True
        )

        self.assertNotContains(response, "more than a year ago")

    def test_editing_cannot_move_the_date_to_the_future(self):
        report = self.create_report()
        tomorrow = timezone.localdate() + timedelta(days=1)

        response = self.client.post(
            reverse("reports:edit_report", args=[report.id]),
            self.report_payload(event_date=tomorrow.isoformat()),
        )

        self.assertContains(response, "The date cannot be in the future.")
        report.refresh_from_db()
        self.assertEqual(report.event_date, timezone.localdate())


class AfterCreatingAReportTests(ReportTestCase):
    def test_the_new_report_is_highlighted_in_my_reports(self):
        self.login_as(self.creator)

        response = self.client.post(
            reverse("reports:create_lost_report"), self.report_payload(), follow=True
        )

        report = ItemReport.objects.get()
        self.assertEqual(response.redirect_chain[-1][0], f"{reverse('reports:my_reports')}#report-{report.id}")
        self.assertContains(response, f'id="report-{report.id}"')
        self.assertContains(response, "Pending Review")


class ContactGuidanceTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.report = self.create_report()
        self.detail_url = reverse("reports:report_detail", args=[self.report.id])

    def test_a_visitor_is_invited_to_log_in_and_comes_back_to_the_report(self):
        login_link = f"{reverse('accounts:login')}?next={self.detail_url}"

        response = self.client.get(self.detail_url)

        self.assertContains(response, login_link)
        response = self.client.post(login_link, {"username": self.other.email, "password": PASSWORD})
        self.assertRedirects(response, self.detail_url)

    def test_a_logged_in_member_sees_the_contact_button_instead(self):
        self.login_as(self.other)

        response = self.client.get(self.detail_url)

        self.assertContains(response, reverse("reports:contact_reporter", args=[self.report.id]))
        self.assertNotContains(response, "Log in to Contact the Reporter")

    def test_the_sender_knows_the_reporter_will_reply_to_their_email(self):
        self.login_as(self.other)

        response = self.client.get(reverse("reports:contact_reporter", args=[self.report.id]))

        self.assertContains(response, "will see your institutional email (other@eafit.edu.co)")

    def test_the_reporter_can_reply_by_email(self):
        ContactMessage.objects.create(report=self.report, sender=self.other, message="I think it is mine")
        self.login_as(self.creator)

        response = self.client.get(self.detail_url)

        self.assertContains(response, "mailto:other@eafit.edu.co?subject=BackToYou%3A%20Lost%20calculator")


class RejectionReasonTests(ReportTestCase):
    def setUp(self):
        super().setUp()
        self.report = self.create_report(status=ItemReport.Status.PENDING_REVIEW)
        self.moderation_url = reverse("administration_moderate_report", args=[self.report.id])
        self.login_as(self.admin)

    def test_rejecting_without_a_reason_asks_for_one(self):
        response = self.client.post(self.moderation_url, {"action": "reject"})

        self.assertContains(response, "Choose a reason before rejecting")
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.PENDING_REVIEW)
        self.assertFalse(ModerationLogEntry.objects.exists())

    def test_the_reason_and_the_note_are_saved_for_the_reporter(self):
        self.client.post(
            self.moderation_url,
            {"action": "reject", "reason": "unclear", "note": "Add a photo of the keyring."},
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.status, ItemReport.Status.REJECTED)
        self.assertEqual(
            self.report.rejection_reason,
            "The description or the photo is not clear enough to recognize the item. Add a photo of the keyring.",
        )

    def test_approving_does_not_require_a_reason(self):
        response = self.client.get(self.moderation_url)

        select = re.search(r"<select[^>]*>", response.content.decode()).group()
        self.assertNotIn("required", select)

    def test_the_reporter_sees_the_reason_in_the_report_and_in_my_reports(self):
        self.client.post(self.moderation_url, {"action": "reject", "reason": "duplicate"})
        self.login_as(self.creator)

        detail = self.client.get(reverse("reports:report_detail", args=[self.report.id]))
        mine = self.client.get(reverse("reports:my_reports"))

        self.assertContains(detail, "There is already a report for this item.")
        self.assertContains(mine, "There is already a report for this item.")

    def test_removing_a_flagged_report_also_explains_why(self):
        active = self.create_report("Wallet", status=ItemReport.Status.ACTIVE)
        ReportFlag.objects.create(report=active, flagged_by=self.other, reason=ReportFlag.Reason.PERSONAL_DATA)

        self.client.post(reverse("administration_flagged_report_remove", args=[active.id]))

        active.refresh_from_db()
        self.assertEqual(active.status, ItemReport.Status.REJECTED)
        self.assertEqual(
            active.rejection_reason,
            "Removed from public view after community flags: Personal data.",
        )
