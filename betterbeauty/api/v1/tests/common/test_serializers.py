import pytest

from django_dynamic_fixture import G

from api.v1.auth.constants import ErrorMessages
from api.v1.common.serializers import (
    NotificationAckSerializer,
    PushNotificationTokenSerializer,
)
from core.models import User, UserRole
from notifications import ErrorMessages as NotificationErrors
from notifications.models import Notification, NotificationChannel


class TestPushNotificationTokenSerializer(object):
    @pytest.mark.django_db
    def test_validate_user_role(self):
        user: User = G(User, role=[UserRole.CLIENT])
        data = {
            'device_registration_id': 'token token',
            'device_type': 'fcm',
            'user_role': 'stylist',
        }
        serializer = PushNotificationTokenSerializer(data=data, context={'user': user})
        assert(not serializer.is_valid(raise_exception=False))
        assert({'code': ErrorMessages.ERR_INCORRECT_USER_ROLE} in
               serializer.errors['field_errors']['user_role'])
        user.role = [UserRole.CLIENT, UserRole.STYLIST]
        user.save()
        serializer = PushNotificationTokenSerializer(data=data, context={'user': user})
        assert(serializer.is_valid())


class TestNotificationAckSerializer(object):

    @pytest.mark.django_db
    def test_validation(self):
        user: User = G(User)

        our_notification = G(
            Notification, channel=NotificationChannel.PUSH,
            user=user
        )
        foreign_notification = G(
            Notification,
        )
        our_sms_notification: Notification = G(
            Notification, channel=NotificationChannel.SMS,
            user=user
        )

        data = {
            'message_uuids': [
                our_notification.uuid,
                our_sms_notification.uuid,
                foreign_notification.uuid
            ]
        }
        serializer = NotificationAckSerializer(data=data, context={'user': user})
        assert(serializer.is_valid(raise_exception=False) is False)
        assert(
            {'code': NotificationErrors.ERR_NOTIFICATION_NOT_FOUND} in
            serializer.errors['field_errors']['message_uuids']
        )
        data = {
            'message_uuids': [
                our_notification.uuid,
            ]
        }
        serializer = NotificationAckSerializer(data=data, context={'user': user})
        assert (serializer.is_valid(raise_exception=False) is True)
