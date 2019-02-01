import datetime

import pytz

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.utils import timezone

from core.models import UserRole
from notifications.models import Notification
from notifications.types import NotificationCode
from salon.models import Stylist

EST_TIMEZONE = pytz.timezone(settings.TIME_ZONE)


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

        send_time_window_start = datetime.time(12, 0)
        send_time_window_end = datetime.time(17, 0)
        code = NotificationCode.DEAL_OF_THE_WEEK_PROMO
        discard_after = timezone.now() + datetime.timedelta(weeks=1)
        target = UserRole.STYLIST
        message = (
            'We added a new feature Deal of the Week. You can now set up one day per '
            'week at a 30% or greater discount to increase visits and drive more traffic!'
        )

        notifications_to_create_list = []

        stylist_has_prior_notifications_subquery = Notification.objects.filter(
            user_id=OuterRef('user__id'), code=code
        )
        eligible_stylists = Stylist.objects.filter(
            user__phone__isnull=False, deactivated_at__isnull=True,
            salon__isnull=False
        ).annotate(
            has_notification_already=Exists(stylist_has_prior_notifications_subquery)
        ).filter(
            has_notification_already=False
        )
        for stylist in eligible_stylists.iterator():
            notifications_to_create_list.append(
                Notification(
                    user=stylist.user,
                    code=code,
                    target=target,
                    message=message,
                    send_time_window_start=send_time_window_start,
                    send_time_window_end=send_time_window_end,
                    send_time_window_tz=stylist.salon.timezone,
                    discard_after=discard_after,
                    data={}
                )
            )
            self.stdout.write('Created notification for {0}'.format(
                stylist
            ))
        # if any notifications were generated - bulk created them
        self.stdout.write('Total {0} notifications were created'.format(
            len(notifications_to_create_list))
        )
        if notifications_to_create_list and not dry_run:
            Notification.objects.bulk_create(notifications_to_create_list)
