import pytest

from django_dynamic_fixture import G

from api.v1.auth.constants import ErrorMessages
from api.v1.common.serializers import PushNotificationTokenSerializer
from core.models import User, UserRole


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
