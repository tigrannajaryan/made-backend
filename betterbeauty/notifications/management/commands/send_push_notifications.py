from django.conf import settings
from django.core.management.base import BaseCommand

from notifications.utils import (
    send_all_push_notifications,
)


class Command(BaseCommand):
    """
    Send all pending push notifications
    """
    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help="Dry-run. Don't actually do anything.",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        if not settings.PUSH_NOTIFICATIONS_ENABLED:
            self.stdout.write('Push notifications are disabled; exiting')
            return
        self.stdout.write('Going to send push notifications now')
        sent, skipped = send_all_push_notifications(stdout=self.stdout, dry_run=dry_run)
        self.stdout.write('{0} notifications sent, {1} skipped'.format(sent, skipped))
