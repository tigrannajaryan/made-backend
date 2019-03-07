import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.template.loader import render_to_string
from django.utils import timezone

from core.models import UserRole
from notifications.models import Notification
from notifications.types import NotificationCode
from notifications.utils import get_unsubscribe_url
from salon.models import Stylist


class Command(BaseCommand):
    """
    One-time management command to send notification about Stylist Payouts
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

        send_time_window_start = datetime.time(12, 0)
        send_time_window_end = datetime.time(17, 0)
        code = NotificationCode.STYLIST_PAYOUT_PROMO
        discard_after = timezone.now() + datetime.timedelta(weeks=1)
        target = UserRole.STYLIST
        message = (
            'You can now receive client payments directly in the Made Pro App! '
            'Add your bank info before your next visit so you get paid promptly '
            'once your visits checkout.'
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
            short_name = stylist.get_short_name()
            unsubscribe_url = get_unsubscribe_url(target, stylist.uuid)
            msg_plain = render_to_string('email/notification/stylist_payout_promo/body.txt',
                                         {'short_name': short_name,
                                          'unsubscribe_url': unsubscribe_url})
            msg_html = render_to_string('email/notification/stylist_payout_promo/body.html',
                                        {'short_name': short_name,
                                         'unsubscribe_url': unsubscribe_url})
            mail_subject = render_to_string('email/notification/stylist_payout_promo/subject.txt',
                                            {'short_name': short_name})
            notifications_to_create_list.append(
                Notification(
                    user=stylist.user,
                    code=code,
                    email_details={
                        'from': settings.DEFAULT_FROM_EMAIL,
                        'to': stylist.email,
                        'subject': mail_subject,
                        'text_content': msg_plain,
                        'html_content': msg_html
                    },
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
