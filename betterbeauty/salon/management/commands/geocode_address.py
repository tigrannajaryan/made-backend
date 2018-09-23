from io import TextIOBase

from django.core.management import BaseCommand
from django.db import transaction

from client.models import Client
from salon.models import Salon


@transaction.atomic()
def geocode_stylist_address(stdout: TextIOBase, dry_run: bool):
    ungeo_coded_salons = Salon.objects.filter(
        last_geo_coded=None).select_for_update(skip_locked=True)
    stdout.write('Found {0} addresses to geocode{1}...'.format(
        len(ungeo_coded_salons),
        ' with dry run' if dry_run else '',
    ))
    for salon in ungeo_coded_salons:
        stdout.write('GeoCoding salon {0} - {1}'.format(
            salon.name, salon.address
        ))
        if not dry_run:
            salon.geo_code_address()


@transaction.atomic()
def geocode_client_zipcode(stdout: TextIOBase, dry_run: bool):
    ungeo_coded_clients = Client.objects.filter(
        last_geo_coded=None).exclude(zip_code__isnull=True).exclude(
        zip_code="").select_for_update(skip_locked=True)
    stdout.write('Found {0} zipcodes to geocode{1}...'.format(
        len(ungeo_coded_clients),
        ' with dry run' if dry_run else '',
    ))
    for client in ungeo_coded_clients:
        stdout.write('GeoCoding client {0}'.format(
            client.user.get_full_name(),
        ))
        if not dry_run:
            client.geo_code_address()


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
        geocode_stylist_address(stdout=self.stdout, dry_run=dry_run)
        geocode_client_zipcode(stdout=self.stdout, dry_run=dry_run)
