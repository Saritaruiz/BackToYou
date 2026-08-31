from django.urls import path
from . import views, views_owner

app_name = "reports" 
urlpatterns = [
    path("", views.report_list, name="report_list"),
    path("lost/new/", views.create_lost_report, name="create_lost_report"),
    path("found/new/", views.create_found_report, name="create_found_report"),
    path("mine/", views_owner.my_reports, name="my_reports"),
    path("<int:report_id>/contact/", views.contact_reporter, name="contact_reporter"),
    path("<int:report_id>/edit/", views_owner.edit_report, name="edit_report"),
    path("<int:report_id>/delete/", views_owner.delete_report, name="delete_report"),
    path(
        "<int:report_id>/recovered/",
        views_owner.mark_report_recovered,
        name="mark_report_recovered",
    ),
    path("<int:report_id>/", views.report_detail, name="report_detail"),
]
# django sabe que cuando alguien entre a la ruta de reportes, debe ejecutar report_list

