import datetime
from io import TextIOBase
from typing import List

import pytz
import unicodecsv
from dateutil import parser

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import User
from notifications.models import Notification, NotificationChannel

EST_TIMEZONE = pytz.timezone(settings.TIME_ZONE)


def import_notification(line: List[str], dry_run: bool, stdout: TextIOBase) -> bool:
    phone, message, sent_at_str, target, code = line
    sent_at: datetime.datetime = EST_TIMEZONE.localize(parser.parse(sent_at_str))
    try:
        user: User = User.objects.get(phone__icontains=phone)
    except User.DoesNotExist:
        stdout.write('---> Could not find a user with phone {0}, skipping'.format(phone))
        return False
    stdout.write('Creating [{0}] notification for phone {1}'.format(
        code, phone
    ))
    if not dry_run:
        notification, created = Notification.objects.get_or_create(
            target=target,
            code=code,
            message=message,
            user=user,
            defaults={
                'sent_at': sent_at,
                'discard_after': sent_at,
                'send_time_window_start': sent_at.time(),
                'send_time_window_end': sent_at.time(),
                'send_time_window_tz': EST_TIMEZONE,
                'sent_via_channel': NotificationChannel.SMS,
                'pending_to_send': False,
            }
        )
        if not created:
            stdout.write('---> Notification already exists, skipping')
        return created
    return False


class Command(BaseCommand):
    """
    One-time management command for importing previously sent SMS notifications from csv.
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
            '-i', '--infile', dest='infile',
            help='Input file for order IDs (optional)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        num_imported = 0
        skipped = 0
        num_processed = 0

        infile = options.get('infile')
        if not infile:
            return

        with open(infile, 'rb') as input_file:
            reader = unicodecsv.reader(input_file)
            for idx, line in enumerate(reader):
                if idx == 0:
                    continue
                num_processed += 1
                result = import_notification(line, dry_run=dry_run, stdout=self.stdout)
                if result:
                    num_imported += 1
                else:
                    skipped += 1
            self.stdout.write(
                '{0} notifications were processed; {1} imported, {2} skipped'.format(
                    num_processed, num_imported, skipped
                )
            )
