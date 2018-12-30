import logging
from io import TextIOBase

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.constants import EnvLevel
from notifications.types import NotificationCode
from notifications.utils import (
    generate_hint_to_first_book_notifications,
    generate_hint_to_rebook_notifications,
    generate_hint_to_select_stylist_notifications,
    generate_remind_add_photo_notifications,
    generate_remind_invite_clients_notifications,
    generate_stylist_registration_incomplete_notifications,
    generate_tomorrow_appointments_notifications,
    send_all_notifications,
)


logger = logging.getLogger(__name__)


def stdout_and_log(message: str, stdout: TextIOBase):
    """Output message to both stdout and configured logger"""
    stdout.write(message)
    logger.info(message)


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
        if not settings.NOTIFICATIONS_ENABLED:
            self.stdout.write('Notifications are disabled, exiting')
            return

        stdout_and_log(
            'Generating {0} notifications'.format(NotificationCode.HINT_TO_FIRST_BOOK),
            self.stdout
        )
        time_start = timezone.now()
        notification_count = generate_hint_to_first_book_notifications(dry_run=dry_run)
        time_end = timezone.now()
        stdout_and_log('...{0} {2} notifications generated; took {1} seconds'.format(
            notification_count, (time_end - time_start).total_seconds(),
            NotificationCode.HINT_TO_FIRST_BOOK
        ), self.stdout)

        stdout_and_log(
            'Generating {0} notifications'.format(NotificationCode.HINT_TO_SELECT_STYLIST),
            self.stdout
        )
        time_start = timezone.now()
        notification_count = generate_hint_to_select_stylist_notifications(dry_run=dry_run)
        time_end = timezone.now()
        stdout_and_log('...{0} {2} notifications generated; took {1} seconds'.format(
            notification_count, (time_end - time_start).total_seconds(),
            NotificationCode.HINT_TO_SELECT_STYLIST
        ), self.stdout)

        stdout_and_log(
            'Generating {0} notifications'.format(NotificationCode.HINT_TO_REBOOK),
            self.stdout
        )
        time_start = timezone.now()
        notification_count = generate_hint_to_rebook_notifications(dry_run=dry_run)
        time_end = timezone.now()
        stdout_and_log('...{0} {2} notifications generated; took {1} seconds'.format(
            notification_count, (time_end - time_start).total_seconds(),
            NotificationCode.HINT_TO_REBOOK
        ), self.stdout)

        stdout_and_log(
            'Generating {0} notifications'.format(NotificationCode.TOMORROW_APPOINTMENTS),
            self.stdout
        )
        time_start = timezone.now()
        notification_count = generate_tomorrow_appointments_notifications(dry_run=dry_run)
        time_end = timezone.now()
        stdout_and_log('...{0} {2} notifications generated; took {1} seconds'.format(
            notification_count, (time_end - time_start).total_seconds(),
            NotificationCode.TOMORROW_APPOINTMENTS
        ), self.stdout)

        stdout_and_log(
            'Generating {0} notifications'.format(NotificationCode.REGISTRATION_INCOMPLETE),
            self.stdout
        )
        time_start = timezone.now()
        notification_count = generate_stylist_registration_incomplete_notifications(
            dry_run=dry_run
        )
        time_end = timezone.now()
        stdout_and_log('...{0} {2} notifications generated; took {1} seconds'.format(
            notification_count, (time_end - time_start).total_seconds(),
            NotificationCode.REGISTRATION_INCOMPLETE
        ), self.stdout)

        stdout_and_log(
            'Generating {0} notifications'.format(NotificationCode.REMIND_INVITE_CLIENTS),
            self.stdout
        )
        time_start = timezone.now()
        notification_count = generate_remind_invite_clients_notifications(
            dry_run=dry_run
        )
        time_end = timezone.now()
        stdout_and_log('...{0} {2} notifications generated; took {1} seconds'.format(
            notification_count, (time_end - time_start).total_seconds(),
            NotificationCode.REMIND_INVITE_CLIENTS
        ), self.stdout)

        stdout_and_log(
            'Generating {0} notifications'.format(NotificationCode.REMIND_ADD_PHOTO),
            self.stdout
        )
        if settings.LEVEL != EnvLevel.PRODUCTION:  # TODO: enable on production after testing
            time_start = timezone.now()
            notification_count = generate_remind_add_photo_notifications(
                dry_run=dry_run
            )
            time_end = timezone.now()
            stdout_and_log('...{0} {2} notifications generated; took {1} seconds'.format(
                notification_count, (time_end - time_start).total_seconds(),
                NotificationCode.REMIND_ADD_PHOTO
            ), self.stdout)

        if force_send:
            self.stdout.write('Going to send push notifications now')
            sent, skipped = send_all_notifications(stdout=self.stdout, dry_run=dry_run)
            self.stdout.write('{0} notifications sent, {1} skipped'.format(sent, skipped))
