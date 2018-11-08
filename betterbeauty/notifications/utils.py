from io import TextIOBase

from .models import Notification
from .types import NotificationChannel


def send_all_push_notifications(stdout: TextIOBase, dry_run: bool=True):
    """Send (or pretend if dry_run is True) ALL pending push notifications"""
    pending_notifications = Notification.objects.filter(
        user__is_active=True, pending_to_send=False, is_sent__isnull=False,
        channel=NotificationChannel.PUSH
    ).select_for_update(skip_locked=True)
    for notification in pending_notifications.iterator():
        stdout.write('Going to send {0}'.format(notification.__str__()))
        if not dry_run:
            result = notification.send_and_mark_sent_push_notification_now()
            if result:
                stdout.write('..sent successfully')
            else:
                stdout.write('..failed to send')
