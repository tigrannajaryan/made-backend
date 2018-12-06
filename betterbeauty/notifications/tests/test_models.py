import datetime

import mock
import pytest
import pytz

from django.conf import settings
from django.test import override_settings
from django_dynamic_fixture import G
from freezegun import freeze_time
from push_notifications.models import APNSDevice

from core.models import User, UserRole
from integrations.push.types import MobileAppIdType
from notifications.models import Notification, NotificationChannel
from notifications.settings import NOTIFICATION_CHANNEL_PRIORITY


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
    @override_settings(NOTIFICATIONS_ENABLED=True)
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

    @pytest.mark.django_db
    @freeze_time('2018-11-07 10:30:00 UTC')  # 5:30 am EST
    @override_settings(TWILIO_SMS_ENABLED=True)
    @mock.patch('notifications.models.send_sms_message')
    def test_send_and_mark_sent_sms_now(self, twilio_mock):
        our_user: User = G(User, role=[UserRole.CLIENT])
        notification: Notification = G(
            Notification, user=our_user, sent_at=None, code='our_code',
            message='some message', target=UserRole.CLIENT,
            send_time_window_start=datetime.time(10, 0),
            send_time_window_end=datetime.time(11, 0),
            send_time_window_tz=pytz.UTC,
            discard_after=datetime.datetime(2019, 1, 1, 0, 0, tzinfo=pytz.UTC))
        notification.send_and_mark_sent_sms_now()
        twilio_mock.assert_called_once_with(
            to_phone=our_user.phone,
            body=notification.message,
            role=UserRole.CLIENT
        )
        notification.refresh_from_db()
        assert(notification.sent_via_channel == NotificationChannel.SMS)
        assert(notification.pending_to_send is False)
        assert(notification.sent_at is not None)

    @pytest.mark.django_db
    @mock.patch.object(Notification, 'send_and_mark_sent_sms_now')
    @mock.patch.object(Notification, 'send_and_mark_sent_push_notification_now')
    def test_send_and_mark_sent_now(self, push_mock, sms_mock, mocker):
        channel_selector_mock = mocker.patch.object(
            Notification, 'get_channel_to_send_over', mock.MagicMock()
        )
        channel_selector_mock.return_value = NotificationChannel.SMS
        our_user: User = G(User, role=[UserRole.CLIENT])
        notification: Notification = G(
            Notification, user=our_user, sent_at=None, code='our_code',
            message='some message', target=UserRole.CLIENT,
            discard_after=datetime.datetime(2019, 1, 1, 0, 0, tzinfo=pytz.UTC))
        notification.send_and_mark_sent_now()
        push_mock.assert_not_called()
        sms_mock.assert_called_once_with()

        sms_mock.reset_mock()
        channel_selector_mock.return_value = NotificationChannel.PUSH
        notification.send_and_mark_sent_now()
        push_mock.assert_called_once_with()
        sms_mock.assert_not_called()

    @pytest.mark.django_db
    def test_can_send_over_channel(self):
        our_user: User = G(User, role=[UserRole.CLIENT, UserRole.STYLIST])
        notification: Notification = G(
            Notification, user=our_user, sent_at=None, code='our_code',
            message='some message', target=UserRole.CLIENT,
            discard_after=datetime.datetime(2019, 1, 1, 0, 0, tzinfo=pytz.UTC))
        with override_settings(NOTIFICATIONS_ENABLED=True):
            with mock.patch.dict(NOTIFICATION_CHANNEL_PRIORITY, {
                'our_code': [NotificationChannel.PUSH]
            }):
                assert(
                    notification.can_send_over_channel(NotificationChannel.PUSH) is False
                )
                G(APNSDevice, user=our_user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
                assert (
                    notification.can_send_over_channel(NotificationChannel.PUSH) is True
                )
                notification.target = UserRole.STYLIST
                notification.save()
                assert (
                    notification.can_send_over_channel(NotificationChannel.PUSH) is False
                )
                G(APNSDevice, user=our_user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
                assert (
                    notification.can_send_over_channel(NotificationChannel.PUSH) is True
                )
        with override_settings(TWILIO_SMS_ENABLED=True, NOTIFICATIONS_ENABLED=True):
            with mock.patch.dict(NOTIFICATION_CHANNEL_PRIORITY, {
                'our_code': [NotificationChannel.PUSH]
            }):
                assert(notification.can_send_over_channel(NotificationChannel.SMS) is False)
            with mock.patch.dict(NOTIFICATION_CHANNEL_PRIORITY, {
                'our_code': [NotificationChannel.PUSH, NotificationChannel.SMS]
            }):
                assert (notification.can_send_over_channel(NotificationChannel.SMS) is False)
                our_user.phone = '12345'
                our_user.save()
                assert (notification.can_send_over_channel(NotificationChannel.SMS) is True)

    @pytest.mark.django_db
    @override_settings(TWILIO_SMS_ENABLED=True, NOTIFICATIONS_ENABLED=True)
    def test_get_channel_to_send_over(self):
        our_user: User = G(User, role=[UserRole.CLIENT, UserRole.STYLIST])
        notification: Notification = G(
            Notification, user=our_user, sent_at=None, code='our_code',
            message='some message', target=UserRole.CLIENT,
            discard_after=datetime.datetime(2019, 1, 1, 0, 0, tzinfo=pytz.UTC))
        with mock.patch.dict(NOTIFICATION_CHANNEL_PRIORITY, {
            'our_code': [NotificationChannel.PUSH]
        }):
            # it's only push, and no devices are there
            assert(notification.get_channel_to_send_over() is None)
            G(APNSDevice, user=our_user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
            assert (notification.get_channel_to_send_over() == NotificationChannel.PUSH)
        APNSDevice.objects.all().delete()
        with mock.patch.dict(NOTIFICATION_CHANNEL_PRIORITY, {
            'our_code': [NotificationChannel.PUSH, NotificationChannel.SMS]
        }):
            # it's only push, and no devices are there
            assert (notification.get_channel_to_send_over() is None)
            our_user.phone = '12345'
            our_user.save()
            assert(notification.get_channel_to_send_over() is NotificationChannel.SMS)
            # add push device, and it should take priority
            G(APNSDevice, user=our_user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
            assert (notification.get_channel_to_send_over() == NotificationChannel.PUSH)
