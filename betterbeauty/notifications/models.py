import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone

from timezone_field import TimeZoneField

from client.models import Client
from core.choices import CLIENT_OR_STYLIST_ROLE
from core.models import User, UserRole
from integrations.push.utils import (
    has_push_notification_device,
    send_message_to_apns_devices_of_user,
    send_message_to_fcm_devices_of_user
)
from integrations.twilio import send_sms_message
from notifications.settings import NOTIFICATION_CHANNEL_PRIORITY
from salon.models import Stylist
from .types import (
    NOTIFICATION_CHANNEL_CHOICES,
    NotificationChannel,
)

logger = logging.getLogger(__name__)


def default_json_field_value():
    return {}


class Notification(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='notifications',
        related_query_name='notification'
    )
    target = models.CharField(choices=CLIENT_OR_STYLIST_ROLE, max_length=16)
    code = models.CharField(max_length=64, verbose_name='Notification code')
    message = models.CharField(max_length=1024)
    sms_message = models.CharField(max_length=1024, blank=True, null=True, default=None)
    # email_details JSON will contain from, to, subject and text_content, html_content
    email_details = JSONField(default=default_json_field_value, blank=True, null=True)
    data = JSONField(default=default_json_field_value, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    send_time_window_start = models.TimeField()
    send_time_window_end = models.TimeField()
    send_time_window_tz = TimeZoneField(default=settings.TIME_ZONE)
    pending_to_send = models.BooleanField(default=True)
    sent_at = models.DateTimeField(null=True, default=None, blank=True)
    sent_via_channel = models.CharField(
        max_length=16, null=True, choices=NOTIFICATION_CHANNEL_CHOICES,
        default=None, blank=True
    )

    discard_after = models.DateTimeField()
    device_acked_at = models.DateTimeField(null=True, default=None, editable=False)
    # deprecated field. notifications.settings.NOTIFICATION_CHANNEL_PRIORITY must
    # be used to indicate which channel to send over
    channel = models.CharField(
        max_length=16, null=True, choices=NOTIFICATION_CHANNEL_CHOICES,
        default=NotificationChannel.PUSH
    )

    forced_channel = models.CharField(
        verbose_name='Specifically selected channel for current notification',
        max_length=16, null=True, blank=True, choices=NOTIFICATION_CHANNEL_CHOICES,
        default=None
    )

    twilio_message_id = models.CharField(max_length=255, null=True, blank=True, default=None)

    class Meta:
        db_table = 'notification'

    def __str__(self):
        return '{0} -> {1} {2}'.format(
            self.code, self.target, self.user.__str__()
        )

    def can_send_now(self) -> bool:
        if not self.pending_to_send:
            return False
        if timezone.now() > self.discard_after:
            self.pending_to_send = False
            self.save(update_fields=['pending_to_send', ])
            return False
        current_time = timezone.now().astimezone(self.send_time_window_tz).time()
        if not self.send_time_window_start <= current_time <= self.send_time_window_end:
            return False
        return True

    def send_and_mark_sent_push_notification_now(self) -> bool:
        """Send push notification to all devices of the user and mark message as sent"""
        if not settings.NOTIFICATIONS_ENABLED:
            return False
        if not self.can_send_now():
            return False

        user: User = self.user
        extra: Dict[str, Any] = {
            'code': self.code,
            'uuid': str(self.uuid)
        }
        if self.data:
            extra.update(self.data)

        # bulk send message to all configured APNS and GCM/FCM installed apps matching target
        send_message_to_apns_devices_of_user(
            user=user, user_role=self.target, message=self.message,
            badge_count=0, extra=extra
        )
        send_message_to_fcm_devices_of_user(
            user=user, user_role=self.target, message=self.message,
            badge_count=0, extra=extra
        )

        # mark message as sent
        self.sent_via_channel = NotificationChannel.PUSH
        self.sent_at = timezone.now()
        self.pending_to_send = False
        self.save(
            update_fields=['sent_via_channel', 'sent_at', 'pending_to_send', ])
        return True

    def get_sms_message(self):
        return self.sms_message if self.sms_message else self.message

    def send_and_mark_sent_sms_now(self) -> bool:
        """Send SMS message to the user and mark message as sent"""
        if not self.can_send_now():
            return False

        user: User = self.user
        message_sid = send_sms_message(
            to_phone=user.phone,
            body=self.get_sms_message(),
            role=self.target
        )

        # mark message as sent
        self.sent_via_channel = NotificationChannel.SMS
        self.sent_at = timezone.now()
        self.pending_to_send = False
        self.twilio_message_id = message_sid
        self.save(
            update_fields=[
                'sent_via_channel', 'sent_at', 'pending_to_send', 'twilio_message_id',
            ])
        return True

    def send_and_mark_sent_email_now(self) -> bool:

        if not self.can_send_now():
            return False
        if 'to' in self.email_details and self.email_details['to']:
            mails_count = send_mail(
                self.email_details['subject'],
                self.email_details['text_content'],
                self.email_details['from'],
                [self.email_details['to']],
                html_message=self.email_details['html_content'],
                fail_silently=False,
            )
            logger.info('{0} email notification sent to {1}'.format(mails_count,
                                                                    self.email_details['to']))
            self.sent_via_channel = NotificationChannel.EMAIL
            self.sent_at = timezone.now()
            self.pending_to_send = False
            self.save(
                update_fields=['sent_via_channel', 'sent_at', 'pending_to_send', ]
            )
            return True
        else:
            return False

    def can_send_over_channel(self, channel: NotificationChannel) -> bool:
        """Verify if notification can be sent over given channel"""
        if not settings.NOTIFICATIONS_ENABLED:
            return False
        if self.code not in NOTIFICATION_CHANNEL_PRIORITY:
            logger.error(
                'Attempted to send a notification with code '
                'not included into priority list: {0}'.format(self.code)
            )
            return False
        if channel not in NOTIFICATION_CHANNEL_PRIORITY[self.code]:
            return False
        if channel == NotificationChannel.PUSH:
            return has_push_notification_device(
                user=self.user, user_role=self.target
            )
        if channel == NotificationChannel.SMS:
            if not self.user.phone or self.user.user_stopped_sms:
                return False
            if self.target == UserRole.CLIENT and hasattr(self.user, 'client'):
                if not self.user.client.sms_notifications_enabled:
                    return False
            return True
        if (channel == NotificationChannel.EMAIL and 'to' in self.email_details and
                self.email_details['to']):
            if self.target == UserRole.CLIENT:
                return Client.objects.filter(email=self.email_details['to'],
                                             email_notifications_enabled=True,
                                             email_verified=True).exists()
            elif self.target == UserRole.STYLIST:
                return Stylist.objects.filter(email=self.email_details['to'],
                                              email_notifications_enabled=True,
                                              email_verified=True).exists()
        return False

    def get_channel_to_send_over(self) -> Optional[NotificationChannel]:
        """Get first available channel based on configured priority and env settings"""
        configured_channels = NOTIFICATION_CHANNEL_PRIORITY[self.code]
        for channel in configured_channels:
            if self.can_send_over_channel(channel):
                return channel
        return None

    def send_and_mark_sent_now(self) -> bool:
        """Send over first available channel and mark as sent"""
        if self.forced_channel:
            channel = self.forced_channel
        else:
            channel = self.get_channel_to_send_over()
        if not channel:
            return False
        if channel == NotificationChannel.SMS:
            return self.send_and_mark_sent_sms_now()
        if channel == NotificationChannel.PUSH:
            return self.send_and_mark_sent_push_notification_now()
        if channel == NotificationChannel.EMAIL:
            return self.send_and_mark_sent_email_now()
        logger.warning(
            'Notification.send_and_mark_sent_now got wrong channel {0}'.format(
                channel
            ))
        return False
