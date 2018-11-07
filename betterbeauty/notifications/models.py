import logging
from typing import Any, Dict
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils import timezone

from timezone_field import TimeZoneField

from core.choices import CLIENT_OR_STYLIST_ROLE
from core.models import User
from integrations.push.utils import (
    send_message_to_apns_devices_of_user,
    send_message_to_fcm_devices_of_user
)
from .types import NOTIFICATION_CNANNEL_CHOICES, NotificationChannel

logger = logging.getLogger(__name__)


def default_json_field_value():
    return {}


class Notification(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    target = models.CharField(choices=CLIENT_OR_STYLIST_ROLE, max_length=16)
    code = models.CharField(max_length=64, verbose_name='Notification code')
    message = models.CharField(max_length=512)
    data = JSONField(default=default_json_field_value, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    send_time_window_start = models.TimeField()
    send_time_window_end = models.TimeField()
    send_time_window_tz = TimeZoneField(default=settings.TIME_ZONE)
    pending_to_send = models.BooleanField(default=True)
    sent_at = models.DateTimeField(null=True, default=None, blank=True)
    discard_after = models.DateTimeField()
    device_acked_at = models.DateTimeField(null=True, default=None, editable=False)
    channel = models.CharField(
        max_length=16, null=True, choices=NOTIFICATION_CNANNEL_CHOICES,
        default=NotificationChannel.PUSH
    )

    def __str__(self):
        return '{0} -> {1} {2}'.format(
            self.code, self.target, self.user.__str__()
        )

    def can_send_now(self) -> bool:
        if not self.pending_to_send:
            print('not pending')
            return False
        if timezone.now() > self.discard_after:
            self.pending_to_send = False
            self.save(update_fields=['pending_to_send', ])
            print('potracheno')
            return False
        current_time = timezone.now().astimezone(self.send_time_window_tz).time()
        if not self.send_time_window_start <= current_time <= self.send_time_window_end:
            print('not in window', self.send_time_window_start,
                  current_time, self.send_time_window_end)
            return False
        return True

    def send_and_mark_sent_push_notification_now(self) -> bool:
        """Send push notification to all devices of the user and mark message as sent"""
        if not settings.PUSH_NOTIFICATIONS_ENABLED:
            return False
        if not self.can_send_now() or self.channel != NotificationChannel.PUSH:
            return False

        user: User = self.user
        extra: Dict[str, Any] = {
            'code': self.code,
            'uuid': str(self.uuid)
        }
        if self.data:
            extra.update(self.data)

        # calculate new badge count (i.e. how many unacknowledged messages
        # user has for given target) + 1 (current message)
        badge_count = Notification.objects.filter(
            user=self.user, target=self.target, device_acked_at__isnull=True,
            sent_at__isnull=False, channel=NotificationChannel.PUSH
        ).count() + 1

        # bulk send message to all configured APNS and GCM/FCM installed apps matching target
        send_message_to_apns_devices_of_user(
            user=user, user_role=self.target, message=self.message,
            badge_count=badge_count, extra=extra
        )
        send_message_to_fcm_devices_of_user(
            user=user, user_role=self.target, message=self.message,
            badge_count=badge_count, extra=extra
        )

        # mark message as sent
        self.sent_at = timezone.now()
        self.pending_to_send = False
        self.save(update_fields=['sent_at', 'pending_to_send', ])
        return True
