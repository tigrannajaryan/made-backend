from django.contrib import admin, messages

from integrations.push.utils import has_push_notification_device
from .models import Notification


class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'user', 'target', 'pending_to_send',
        'sent_via_channel', 'sent_at', 'device_acked_at',
    ]
    list_filter = ['code', 'target', 'channel', ]
    readonly_fields = ['sent_at', 'device_acked_at', ]
    actions = ['send_push_notification', ]
    raw_id_fields = ['user', ]

    class Meta:
        model = Notification

    def send_push_notification(self, request, queryset):
        errors = []
        for notification in queryset:
            if not notification.can_send_now():
                errors.append('{0} cannot be sent now'.format(notification))
                continue
            if not has_push_notification_device(notification.user, notification.target):
                errors.append('Failed to send {0}: user {1} has no push-enabled devices'.format(
                    notification, notification.user
                ))
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
