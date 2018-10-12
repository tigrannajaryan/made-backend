from django.contrib import admin

from .models import Client, PreferredStylist


class PreferredStylistAdmin(admin.ModelAdmin):
    list_display = ['stylist', 'client']


admin.site.register(Client)
admin.site.register(PreferredStylist, PreferredStylistAdmin)
