from django.conf import settings
from django.core.management.base import BaseCommand

from appointment.utils import (
    clean_up_cancelled_client_calendar_events,
    clean_up_cancelled_stylist_calendar_events,
    generate_client_calendar_events_for_new_appointments,
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
        dry_run = options['dry_run']
        if not settings.GOOGLE_CALENDAR_STYLIST_SYNC_ENABLED:
            self.stdout.write(
                'Synchronization with Stylist calendars '
                'is disabled in {0} environment'.format(
                    settings.LEVEL
                ))
        else:
            generate_stylist_calendar_events_for_new_appointments(
                stdout=self.stdout, dry_run=dry_run
            )
            clean_up_cancelled_stylist_calendar_events(
                stdout=self.stdout, dry_run=dry_run
            )

        if not settings.GOOGLE_CALENDAR_CLIENT_SYNC_ENABLED:
            self.stdout.write(
                'Synchronization with Client calendars '
                'is disabled in {0} environment'.format(
                    settings.LEVEL
                ))
        else:
            generate_client_calendar_events_for_new_appointments(
                stdout=self.stdout, dry_run=dry_run
            )
            clean_up_cancelled_client_calendar_events(
                stdout=self.stdout, dry_run=dry_run
            )
