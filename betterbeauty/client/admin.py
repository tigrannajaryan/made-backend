from django.contrib import admin

from salon.models import Stylist
from .models import Client, ClientOfStylist, PreferredStylist


class ClientOfStylistAdmin(admin.ModelAdmin):
    list_display = ['stylist', 'client', 'created_at']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "stylist":
            kwargs["queryset"] = Stylist.objects.order_by('user__email')
        if db_field.name == "client":
            kwargs["queryset"] = Client.objects.order_by('user__first_name', 'user__last_name')
        return super(
            ClientOfStylistAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


class PreferredStylistAdmin(admin.ModelAdmin):
    list_display = ['stylist', 'client']


admin.site.register(Client)
admin.site.register(ClientOfStylist, ClientOfStylistAdmin)
admin.site.register(PreferredStylist, PreferredStylistAdmin)
