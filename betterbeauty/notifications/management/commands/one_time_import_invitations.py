import datetime
from io import TextIOBase
from typing import List, Optional

import pytz
import unicodecsv
from dateutil import parser

from django.conf import settings
from django.core.management.base import BaseCommand

from client.models import Client
from salon.models import Invitation, InvitationStatus, Stylist

EST_TIMEZONE = pytz.timezone(settings.TIME_ZONE)


def import_invitation(line: List[str], dry_run: bool, stdout: TextIOBase) -> bool:
    client_phone, stylist_name, message, sent_at, stylist_id_str = line
    created_at: datetime.datetime = EST_TIMEZONE.localize(parser.parse(sent_at))
    stylist_id: int = int(stylist_id_str)
    stylist: Stylist = Stylist.objects.get(pk=stylist_id)
    client: Optional[Client] = Client.objects.filter(user__phone__icontains=client_phone).last()
    client_phone_formatted = '+1{0}'.format(
        client_phone
    ) if not client_phone.startswith('+1') else client_phone
    stdout.write('Creating invitation from {0} to {1}'.format(
        stylist, client or client_phone_formatted
    ))
    if not dry_run:
        invitation, created = Invitation.objects.get_or_create(
            phone=client_phone_formatted,
            stylist=stylist,
            created_client=client,
            defaults={
                'status': InvitationStatus.ACCEPTED if client else InvitationStatus.INVITED,
                'accepted_at': client.created_at if client else None,
                'created_at': created_at
            }
        )
        if not created:
            stdout.write('---> Invitation already exists, skipping')
        return created
    return False


class Command(BaseCommand):
    """
    One-time management command to import previously sent invitations from a CSV
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
                result = import_invitation(line, dry_run=dry_run, stdout=self.stdout)
                if result:
                    num_imported += 1
                else:
                    skipped += 1
            self.stdout.write(
                '{0} notifications were processed; {1} imported, {2} skipped'.format(
                    num_processed, num_imported, skipped
                )
            )
