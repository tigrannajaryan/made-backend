from django.conf import settings
from django.core.management.base import BaseCommand

from appointment.utils import (
    clean_up_cancelled_stylist_calendar_events,
    generate_stylist_calendar_events_for_new_appointments
)


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '-d',
            '--dry-run',
            action='store_true',
            dest='dry_run',
            help="Dry-run. Don't actually do anything.",
        )

    def handle(self, *args, **options):
        if not settings.GOOGLE_CALENDAR_STYLIST_SYNC_ENABLED:
            self.stdout.write(
                'Synchronization with Stylist calendars '
                'is disabled in {0} environment'.format(
                    settings.LEVEL
                ))
            return
        dry_run = options['dry_run']
        generate_stylist_calendar_events_for_new_appointments(
            stdout=self.stdout, dry_run=dry_run
        )
        clean_up_cancelled_stylist_calendar_events(
            stdout=self.stdout, dry_run=dry_run
        )
