from django.urls import path
from . import views

app_name = "reports" 
urlpatterns = [
    path("", views.report_list, name="report_list"),
    path("lost/new/", views.create_lost_report, name="create_lost_report"),
    path("found/new/", views.create_found_report, name="create_found_report"),
    path("<int:report_id>/contact/", views.contact_reporter, name="contact_reporter"),
    path("<int:report_id>/", views.report_detail, name="report_detail"),
]
# django sabe que cuando alguien entre a la ruta de reportes, debe ejecutar report_list

