from django.contrib import admin, messages

from .models import Notification
from .types import NotificationChannel


class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'channel', 'user', 'target', 'pending_to_send',
        'sent_at', 'device_acked_at',
    ]
    list_filter = ['code', 'target', 'channel', ]
    readonly_fields = ['sent_at', 'device_acked_at', ]
    actions = ['send_push_notification', ]

    class Meta:
        model = Notification

    def send_push_notification(self, request, queryset):
        errors = []
        for notification in queryset:
            if not notification.can_send_now():
                errors.append('{0} cannot be sent now'.format(notification))
                continue
            if notification.channel != NotificationChannel.PUSH:
                errors.append('{0} is not a Push notification'.format(notification))
                continue
            if not notification.send_and_mark_sent_push_notification_now():
                errors.append('Failed to send {0}'.format(notification))
        if errors:
            self.message_user(
                request,
                level=messages.ERROR,
                message='Some notifications could not be sent: {0}'.format(
                    '; '.join(errors)
                )
            )
    send_push_notification.short_description = 'Send Push Notification(s)'  # type: ignore


admin.site.register(Notification, NotificationAdmin)
