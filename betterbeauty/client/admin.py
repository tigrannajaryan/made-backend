from django.contrib import admin

from .models import Client, PreferredStylist


class PreferredStylistAdmin(admin.ModelAdmin):
    list_display = ['stylist', 'stylist_phone', 'client', 'client_phone']
    search_fields = ['stylist__user__phone', 'client__user__phone']
    raw_id_fields = ['client', 'stylist']

    def client_phone(self, obj):
        return obj.client.user.phone

    def stylist_phone(self, obj):
        return obj.stylist.user.phone

    def get_queryset(self, request):
        return super(PreferredStylistAdmin, self).get_queryset(request).select_related(
            'stylist__user', 'client__user')

    def delete_model(self, request, obj: PreferredStylist):
        obj.hard_delete()


class ClientAdmin(admin.ModelAdmin):
    list_display = ['user_phone', 'user_name']
    search_fields = ['user__phone', 'user__first_name', 'user__last_name']

    def user_phone(self, obj):
        return obj.user.phone

    def user_name(self, obj):
        return obj.user.get_full_name()


admin.site.register(Client, ClientAdmin)
admin.site.register(PreferredStylist, PreferredStylistAdmin)
