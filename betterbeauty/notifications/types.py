from model_utils import Choices

from core.types import StrEnum


class NotificationChannel(StrEnum):
    SMS = 'sms'
    PUSH = 'push'


NOTIFICATION_CNANNEL_CHOICES = Choices(
    (NotificationChannel.SMS.value, 'sms', 'SMS message'),
    (NotificationChannel.PUSH.value, 'push', 'Push Notification'),
)