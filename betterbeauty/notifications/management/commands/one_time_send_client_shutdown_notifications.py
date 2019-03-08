import datetime

import pytz
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef
from django.template.loader import render_to_string
from django.utils import timezone

from appointment.models import Appointment
from client.models import Client
from core.models import UserRole
from notifications.models import Notification
from notifications.types import NotificationCode
from notifications.utils import get_unsubscribe_url


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

        send_time_window_start = datetime.time(10, 0)
        send_time_window_end = datetime.time(17, 0)
        code = NotificationCode.CLIENT_SHUTDOWN
        discard_after = timezone.now() + datetime.timedelta(weeks=1)
        target = UserRole.CLIENT
        message = (
            'Important message about the MadePro app: https://www.madebeauty.com/to-clients/'
        )

        notifications_to_create_list = []

        client_has_prior_notifications_subquery = Notification.objects.filter(
            user_id=OuterRef('user__id'), code=code
        )
        client_has_appointment_subquery = Appointment.objects.filter(
            client_id=OuterRef('id')
        )
        eligible_clients = Client.objects.filter(
            user__phone__isnull=False, email_verified=True,
        ).annotate(
            has_notification_already=Exists(client_has_prior_notifications_subquery),
            has_appointments=Exists(client_has_appointment_subquery)
        ).filter(
            has_notification_already=False,
            has_appointments=True
        )
        for client in eligible_clients.iterator():
            short_name = client.user.get_short_name()
            unsubscribe_url = get_unsubscribe_url(target, client.uuid)
            msg_plain = render_to_string('email/notification/client_shutdown/body.txt',
                                         {'short_name': short_name,
                                          'unsubscribe_url': unsubscribe_url})
            msg_html = render_to_string('email/notification/client_shutdown/body.html',
                                        {'short_name': short_name,
                                         'unsubscribe_url': unsubscribe_url})
            mail_subject = render_to_string('email/notification/client_shutdown/subject.txt')
            notifications_to_create_list.append(
                Notification(
                    user=client.user,
                    code=code,
                    email_details={
                        'from': settings.DEFAULT_FROM_EMAIL,
                        'to': client.email,
                        'subject': mail_subject,
                        'text_content': msg_plain,
                        'html_content': msg_html
                    },
                    target=target,
                    message=message,
                    send_time_window_start=send_time_window_start,
                    send_time_window_end=send_time_window_end,
                    send_time_window_tz=pytz.timezone(settings.TIME_ZONE),
                    discard_after=discard_after,
                    data={}
                )
            )
            self.stdout.write('Created notification for {0}'.format(
                client
            ))
        # if any notifications were generated - bulk created them
        self.stdout.write('Total {0} notifications were created'.format(
            len(notifications_to_create_list))
        )
        if notifications_to_create_list and not dry_run:
            Notification.objects.bulk_create(notifications_to_create_list)
