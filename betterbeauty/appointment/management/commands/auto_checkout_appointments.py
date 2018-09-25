import datetime
from io import TextIOBase
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from appointment.models import Appointment
from appointment.types import AppointmentStatus
from core.models import User
from core.types import UserRole


APPOINTMENT_UPDATE_USER_EMAIL = 'auto_appointment_updater@madebeauty.com'
APPOINTMENT_AUTO_CHECKOUT_INTERVAL = datetime.timedelta(hours=24)


@transaction.atomic
def get_updating_user(stdout: TextIOBase, dry_run: bool) -> Optional[User]:
    if dry_run:
        return None

    updating_user: Optional[User] = User.objects.filter(
        email=APPOINTMENT_UPDATE_USER_EMAIL
    ).last()
    if updating_user:
        stdout.write('User with email {0} already exists; skipping creation'.format(
            APPOINTMENT_UPDATE_USER_EMAIL
        ))
        return updating_user

    stdout.write('Created updating user with email {0}'.format(
        APPOINTMENT_UPDATE_USER_EMAIL
    ))
    updating_user = User.objects.create(
        email=APPOINTMENT_UPDATE_USER_EMAIL,
        role=[UserRole.STAFF, ]
    )
    updating_user.set_unusable_password()
    return updating_user


def auto_checkout_appointments(stdout: TextIOBase, dry_run: bool):
    updating_user: Optional[User] = get_updating_user(stdout=stdout, dry_run=dry_run)
    assert bool(updating_user) != dry_run
    with transaction.atomic():
        appointments_to_update = Appointment.objects.filter(
            status=AppointmentStatus.NEW,
            datetime_start_at__lt=timezone.now() - APPOINTMENT_AUTO_CHECKOUT_INTERVAL
        ).select_for_update(
            skip_locked=True
        )
        for appointment in appointments_to_update:
            action = 'checking out' if not dry_run else 'pretending to check out'
            stdout.write('Appointment with id={0} created on {1}, {2}'.format(
                appointment.id,
                appointment.created_at,
                action
            ))
            if not dry_run:
                appointment.set_status(
                    status=AppointmentStatus.CHECKED_OUT,
                    updated_by=updating_user
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
        auto_checkout_appointments(stdout=self.stdout, dry_run=dry_run)
