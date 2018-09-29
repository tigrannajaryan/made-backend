
import os
from io import TextIOBase
from typing import Optional, Tuple

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.constants import EnvLevel
from core.models import User
from core.types import UserRole


SUPERUSER_EMAILS_BY_LEVEL = {
    EnvLevel.STAGING: 'admin@betterbeauty.io',
    EnvLevel.PRODUCTION: 'admin@madebeauty.com',
}

SUPERUSER_PASSWORD_ENV_VAR_NAME = 'DJANGO_SUPERUSER_PASSWORD'
MIN_PASSWORD_LENGTH = 12


@transaction.atomic
def update_or_create_superuser(
        level: EnvLevel, stdout: TextIOBase, dry_run: bool
) -> Tuple[Optional[User], bool]:

    superuser_email = SUPERUSER_EMAILS_BY_LEVEL[level]
    superuser_password = os.environ.get(SUPERUSER_PASSWORD_ENV_VAR_NAME, '').strip()
    if not superuser_password or len(superuser_password) < MIN_PASSWORD_LENGTH:
        stdout.write(
            '{0} is not set or too short (must be at least {1} chars), skipping...'.format(
                SUPERUSER_PASSWORD_ENV_VAR_NAME, MIN_PASSWORD_LENGTH
            )
        )
        return None, False

    created = False

    superuser: Optional[User] = User.objects.filter(email=superuser_email).last()
    if superuser:
        stdout.write('Superuser already exists, just updating the password')
        if not dry_run:
            superuser.set_password(superuser_password)
            superuser.save(update_fields=['password'])
    else:
        created = True
        stdout.write('Superuser does not exist yet, going to create...')
        if not dry_run:
            superuser = User.objects.create_superuser(
                email=superuser_email,
                password=superuser_password,
                role=[UserRole.STAFF]
            )
    return superuser, created


class Command(BaseCommand):
    """
    Custom command to create superuser in non-interactive mode, with password
    set in the environment variable. We need to be able to automatically create
    a superuser for staging and production, yet standard Django's createsuperuser
    command is not capable of running in non-interactive mode, nor it is able to
    amend existing superuser's password. This command aims to solve this.
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
        level = settings.LEVEL
        if level not in [EnvLevel.STAGING, EnvLevel.PRODUCTION]:
            self.stdout.write('The command must be run only on staging or production')
            return

        update_or_create_superuser(level=level, stdout=self.stdout, dry_run=dry_run)
