from django.urls import path

from .views import create as create_views
from .views import owner as owner_views
from .views import public as public_views

app_name = "reports"

urlpatterns = [
    path("", public_views.report_list, name="report_list"),
    path("lost/new/", create_views.create_lost_report, name="create_lost_report"),
    path("found/new/", create_views.create_found_report, name="create_found_report"),
    path("mine/", owner_views.my_reports, name="my_reports"),
    path(
        "<int:report_id>/contact/",
        public_views.contact_reporter,
        name="contact_reporter",
    ),
    path("<int:report_id>/edit/", owner_views.edit_report, name="edit_report"),
    path("<int:report_id>/delete/", owner_views.delete_report, name="delete_report"),
    path(
        "<int:report_id>/recovered/",
        owner_views.mark_report_recovered,
        name="mark_report_recovered",
    ),
    path("<int:report_id>/", public_views.report_detail, name="report_detail"),
]
