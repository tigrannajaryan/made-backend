from io import TextIOBase

from django.conf import settings
from django.core.management import BaseCommand
from django.db import transaction

from api.common.utils import send_email_verification
from client.models import Client
from core.constants import EnvLevel
from core.types import UserRole
from salon.models import Stylist


@transaction.atomic
def one_time_send_verification_emails(
        stdout: TextIOBase, dry_run: bool
):
    level = settings.LEVEL
    if not level == EnvLevel.PRODUCTION:
        dry_run = True
    stylists = Stylist.objects.filter(email__isnull=False, email_verified=False,
                                      deactivated_at__is_null=True).exclude(email='')
    clients = Client.objects.filter(email__isnull=False, email_verified=False).exclude(email='')
    stylist_emails_sent = 0
    for stylist in stylists:
        if not dry_run:
            send_email_verification(stylist, UserRole.STYLIST)
        stdout.write('Verification email sent to stylists {0}'.format(stylist.email))
        stylist_emails_sent += 1
    client_emails_sent = 0
    for client in clients:
        if not dry_run:
            send_email_verification(client, UserRole.CLIENT)
        stdout.write('Verification email sent to client {0}'.format(client.email))
        client_emails_sent += 1
    stdout.write("Emails sent to stylists: {0}, Emails sent to clients: {1}, Total: {2}".format(
        stylist_emails_sent,
        client_emails_sent,
        stylist_emails_sent + client_emails_sent
    ))
    if dry_run:
        stdout.write("You are using dry-run. So no actual emails are sent.")


class Command(BaseCommand):
    """
    Custom command to send one time verification emails.
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
        one_time_send_verification_emails(stdout=self.stdout, dry_run=dry_run)
