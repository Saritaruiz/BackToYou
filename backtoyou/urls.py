"""
URL configuration for backtoyou project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path
from accounts import views as account_views
from reports import views as report_views

def home(request):
    return render(request, "home.html")

urlpatterns = [
    path("", home, name="home"),
    path("administration/", account_views.administration_panel, name="administration"),
    path(
        "administration/reports/pending/",
        report_views.pending_report_list,
        name="administration_pending_reports",
    ),
    path(
        "administration/reports/<int:report_id>/",
        report_views.moderate_report_detail,
        name="administration_moderate_report",
    ),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("reports/", include("reports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    ) 
