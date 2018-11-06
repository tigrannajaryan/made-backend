from uuid import uuid4

from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import JSONField
from timezone_field import TimeZoneField

from core.choices import CLIENT_OR_STYLIST_ROLE
from core.models import User


def default_json_field_value():
    return {}


class Notification(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    target = models.CharField(choices=CLIENT_OR_STYLIST_ROLE, max_length=16)
    code = models.CharField(max_length=64, verbose_name='Notification code')
    message = models.CharField(max_length=512)
    data = JSONField(default=default_json_field_value)
    created_at = models.DateTimeField(auto_now_add=True)
    send_time_window_start = models.TimeField()
    send_time_window_end = models.TimeField()
    send_time_window_tz = TimeZoneField(default=settings.TIME_ZONE)
    pending_to_send = models.BooleanField()
    sent_at = models.DateTimeField(null=True)
    discard_after = models.DateTimeField()
    device_acked_at = models.DateTimeField(null=True)

    def __str__(self):
        return '{0} -> {1} {2}'.format(
            self.code, self.target, self.user.__str__()
        )
