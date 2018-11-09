from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from notifications.types import NotificationCode
from notifications.utils import (
    generate_hint_to_first_book_notifications,
    send_all_push_notifications,
)


class Command(BaseCommand):
    """
    Go over all functions generating notifications, generate notifications
    and then force-send them
    """
    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help="Dry-run. Don't actually do anything.",
        )
        parser.add_argument(
            '-f',
            '--force_send',
            action='store_true',
            dest='force_send',
            help="Actually force-send notifications after generation",
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force_send = options['force_send']

        self.stdout.write(
            'Generating {0} notifications'.format(NotificationCode.HINT_TO_FIRST_BOOK)
        )
        time_start = timezone.now()
        notification_count = generate_hint_to_first_book_notifications(dry_run=dry_run)
        time_end = timezone.now()
        self.stdout.write('...{0} notifications generated; took {1} seconds'.format(
            notification_count, (time_end - time_start).total_seconds()
        ))
        if force_send and settings.PUSH_NOTIFICATIONS_ENABLED:
            self.stdout.write('Going to send push notifications now')
            sent, skipped = send_all_push_notifications(stdout=self.stdout, dry_run=dry_run)
            self.stdout.write('{0} notifications sent, {1} skipped'.format(sent, skipped))
