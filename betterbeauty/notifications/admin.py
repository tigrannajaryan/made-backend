from django.contrib import admin

from .models import Notification


class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'channel', 'user', 'target', 'pending_to_send',
        'sent_at', 'device_acked_at',
    ]
    list_filter = ['code', 'target', 'channel', ]
    readonly_fields = ['sent_at', 'device_acked_at', ]

    class Meta:
        model = Notification


admin.site.register(Notification, NotificationAdmin)
