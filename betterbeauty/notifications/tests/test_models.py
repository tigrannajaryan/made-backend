import datetime

import pytest
import pytz

from django.conf import settings
from django.test import override_settings
from django_dynamic_fixture import G
from freezegun import freeze_time

from core.models import User
from notifications.models import Notification


class TestNotification(object):
    @freeze_time('2018-11-07 10:30:00 UTC')  # 5:30 am EST
    @pytest.mark.django_db
    def test_can_send_now(self):
        notification: Notification = G(
            Notification,
            send_time_window_tz=pytz.timezone(settings.TIME_ZONE),  # New York
            send_time_window_start=datetime.time(5, 40),
            send_time_window_end=datetime.time(6, 0),
            discard_after=datetime.datetime(2019, 1, 1, 0, 0, tzinfo=pytz.UTC)

        )
        assert(notification.can_send_now() is False)
        notification.send_time_window_start = datetime.time(5, 25)
        notification.save()
        assert (notification.can_send_now() is True)
        notification.pending_to_send = False
        notification.save()
        assert (notification.can_send_now() is False)
        notification.pending_to_send = True
        notification.discard_after = datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC)
        notification.save()
        assert (notification.can_send_now() is False)
        notification.refresh_from_db()
        assert(notification.pending_to_send is False)

    @freeze_time('2018-11-07 10:30:00 UTC')  # 5:30 am EST
    @pytest.mark.django_db
    @override_settings(PUSH_NOTIFICATIONS_ENABLED=True)
    def test_send_push_notification_now(self, mocker):
        apns_sender_mock = mocker.patch(
            'notifications.models.send_message_to_apns_devices_of_user'
        )
        gcm_sender_mock = mocker.patch(
            'notifications.models.send_message_to_fcm_devices_of_user')
        our_user: User = G(User)
        # some unsent notification of our user - doesn't add to badge count
        G(Notification, user=our_user, sent_at=None,
          discard_after=datetime.datetime(2019, 1, 1, 0, 0, tzinfo=pytz.UTC))
        # some unsent notification of our user, already discarded
        #  - doesn't add to badge count
        G(Notification, user=our_user, sent_at=None,
          discard_after=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC))
        # some unsent notification of different user - doesn't add to badge count
        G(Notification, user=our_user, sent_at=None)
        # some sent notification, unacknowledged - adds to count
        G(Notification, user=our_user,
          sent_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC))
        # some sent notification, acknowledged - doesn't add to badge count
        G(Notification, user=our_user,
          sent_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
          device_acked_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC)
          )
        notification: Notification = G(  # adds to count
            Notification, user=our_user,
            send_time_window_tz=pytz.timezone(settings.TIME_ZONE),  # New York
            send_time_window_start=datetime.time(5, 0),
            send_time_window_end=datetime.time(6, 0),
            message='my message', data={'gaga': 'roo'}, code='some_code',
            discard_after=datetime.datetime(2019, 1, 1, 0, 0, tzinfo=pytz.UTC)
        )
        assert (notification.can_send_now() is True)
        notification.send_and_mark_sent_push_notification_now()
        apns_sender_mock.assert_called_once_with(
            user=our_user,
            user_role=notification.target,
            message=notification.message,
            badge_count=0,
            extra={
                'code': notification.code,
                'gaga': 'roo',
                'uuid': str(notification.uuid)
            }
        )
        gcm_sender_mock.assert_called_once_with(
            user=our_user,
            user_role=notification.target,
            message=notification.message,
            badge_count=0,
            extra={
                'code': notification.code,
                'gaga': 'roo',
                'uuid': str(notification.uuid)
            }
        )
