from django.contrib import admin

from salon.models import Stylist
from .models import Client, ClientOfStylist


class ClientOfStylistAdmin(admin.ModelAdmin):
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "stylist":
            kwargs["queryset"] = Stylist.objects.order_by('user__email')
        if db_field.name == "client":
            kwargs["queryset"] = Client.objects.order_by('user__first_name', 'user__last_name')
        return super(
            ClientOfStylistAdmin, self).formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(Client)
admin.site.register(ClientOfStylist, ClientOfStylistAdmin)
