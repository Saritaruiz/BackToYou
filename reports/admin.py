from django.contrib import admin
from .models import Category, ContactMessage, ItemReport, ModerationLogEntry, ReportFlag

# crear y revisar reportes desde /admin

admin.site.register(Category)
admin.site.register(ItemReport)
admin.site.register(ContactMessage)
admin.site.register(ReportFlag)


# RF44: el historial se puede consultar en /admin, pero no crear, cambiar ni borrar.
@admin.register(ModerationLogEntry)
class ModerationLogEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "report_title", "administrator_email")
    list_filter = ("action",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
# Register your models here.
