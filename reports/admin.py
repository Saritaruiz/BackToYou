from django.contrib import admin
from .models import Category, ContactMessage, ItemReport

# crear y revisar reportes desde /admin

admin.site.register(Category)
admin.site.register(ItemReport)
admin.site.register(ContactMessage)
# Register your models here.
