from django.contrib import admin

from core.admin import SoftDeletedFilter
from .models import Client, PreferredStylist


class PreferredStylistAdmin(admin.ModelAdmin):
    list_display = [
        'stylist', 'stylist_phone', 'client', 'client_phone', 'deleted_at',
    ]
    search_fields = ['stylist__user__phone', 'client__user__phone']
    raw_id_fields = ['client', 'stylist']
    list_filter = (SoftDeletedFilter, )

    def client_phone(self, obj):
        return obj.client.user.phone

    def stylist_phone(self, obj):
        return obj.stylist.user.phone

    def get_queryset(self, request):
        ordering = self.get_ordering(request)
        qs = self.model.all_objects.get_queryset()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs.select_related(
            'stylist__user', 'client__user')

    def delete_model(self, request, obj: PreferredStylist):
        obj.hard_delete()


class ClientAdmin(admin.ModelAdmin):
    list_display = ['user_phone', 'user_name', 'created_at', ]
    search_fields = ['user__phone', 'user__first_name', 'user__last_name']

    def user_phone(self, obj):
        return obj.user.phone

    def user_name(self, obj):
        return obj.user.get_full_name()


admin.site.register(Client, ClientAdmin)
admin.site.register(PreferredStylist, PreferredStylistAdmin)
