"""Las imagenes no deben quedar huerfanas en MEDIA_ROOT."""

import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Category, ItemReport

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04"
    b"\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
)


class MediaCleanupTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.creator = get_user_model().objects.create_user(
            username="creator@eafit.edu.co",
            email="creator@eafit.edu.co",
            password="StrongPass123",
        )
        self.category = Category.objects.create(name="Electronics")
        self.report = ItemReport.objects.create(
            title="Lost calculator",
            description="Black scientific calculator",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
            image=SimpleUploadedFile("original.png", PNG_BYTES, content_type="image/png"),
        )
        self.client.login(
            username=self.creator.email,
            password="StrongPass123",
        )

    def ruta(self, nombre):
        return os.path.join(self.media_root, nombre.replace("/", os.sep))

    def test_deleting_a_report_removes_its_image_from_disk(self):
        ruta = self.ruta(self.report.image.name)
        self.assertTrue(os.path.exists(ruta))

        self.client.post(reverse("reports:delete_report", args=[self.report.id]))

        self.assertFalse(os.path.exists(ruta))

    def test_replacing_the_image_removes_the_previous_file(self):
        ruta_original = self.ruta(self.report.image.name)
        self.assertTrue(os.path.exists(ruta_original))

        self.client.post(
            reverse("reports:edit_report", args=[self.report.id]),
            {
                "title": "Lost calculator",
                "description": "Black scientific calculator",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Library",
                "image": SimpleUploadedFile(
                    "replacement.png",
                    PNG_BYTES,
                    content_type="image/png",
                ),
            },
        )

        self.report.refresh_from_db()
        self.assertFalse(os.path.exists(ruta_original))
        self.assertTrue(os.path.exists(self.ruta(self.report.image.name)))

    def test_editing_without_touching_the_image_keeps_the_file(self):
        ruta = self.ruta(self.report.image.name)

        self.client.post(
            reverse("reports:edit_report", args=[self.report.id]),
            {
                "title": "Lost calculator (updated)",
                "description": "Black scientific calculator",
                "category": self.category.id,
                "event_date": "2026-08-10",
                "location": "Library",
            },
        )

        self.report.refresh_from_db()
        self.assertEqual(self.report.title, "Lost calculator (updated)")
        self.assertTrue(os.path.exists(ruta))

    def test_deleting_a_report_without_image_does_not_fail(self):
        sin_imagen = ItemReport.objects.create(
            title="Lost umbrella",
            description="Black umbrella",
            category=self.category,
            event_date="2026-08-10",
            location="Library",
            creator=self.creator,
            report_type=ItemReport.ReportType.LOST,
            status=ItemReport.Status.ACTIVE,
        )

        response = self.client.post(
            reverse("reports:delete_report", args=[sin_imagen.id])
        )

        self.assertRedirects(response, reverse("reports:report_list"))
        self.assertFalse(ItemReport.objects.filter(id=sin_imagen.id).exists())
