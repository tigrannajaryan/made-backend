from django.conf import settings

from rest_framework import serializers

from api.common.mixins import FormattedErrorMessageMixin
from api.v1.auth.constants import ErrorMessages
from core.models import TemporaryFile, User
from core.types import UserRole
from integrations.google.types import (
    GoogleIntegrationErrors,
    GoogleIntegrationType,
)
from integrations.push.types import PUSH_NOTIFICATION_TOKEN_CHOICES
from notifications import ErrorMessages as NotificationErrors
from notifications.models import Notification, NotificationChannel


class TemporaryImageSerializer(serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)
    file = serializers.ImageField(write_only=True)

    class Meta:
        model = TemporaryFile
        fields = ['file', 'uuid', ]

    def validate_file(self, file):
        if file.size > settings.MAX_FILE_UPLOAD_SIZE:
            raise serializers.ValidationError('File is too big, max. size {0} bytes'.format(
                settings.MAX_FILE_UPLOAD_SIZE
            ))
        return file

    def save(self, **kwargs):
        uploaded_by: User = self.context['user']
        return super(TemporaryImageSerializer, self).save(
            uploaded_by=uploaded_by, **kwargs
        )


class PushNotificationTokenSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    device_registration_id = serializers.CharField(
        required=True, allow_null=False, allow_blank=False
    )
    device_type = serializers.ChoiceField(choices=PUSH_NOTIFICATION_TOKEN_CHOICES)
    user_role = serializers.CharField(required=True, allow_null=False, allow_blank=False)
    is_development_build = serializers.BooleanField(required=False)

    def validate_user_role(self, role: UserRole):
        user: User = self.context['user']
        if role not in user.role or role not in [UserRole.STYLIST, UserRole.CLIENT]:
            raise serializers.ValidationError(ErrorMessages.ERR_INCORRECT_USER_ROLE)
        return role


class NotificationAckSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    message_uuids = serializers.ListField(child=serializers.UUIDField())

    def validate_message_uuids(self, message_uuids):
        user: User = self.context['user']
        errors = []
        for uuid in message_uuids:
            notification = Notification.objects.filter(
                uuid=str(uuid), user=user
            ).last()
            if not notification:
                errors.append(NotificationErrors.ERR_NOTIFICATION_NOT_FOUND)
                continue
            if notification.sent_via_channel != NotificationChannel.PUSH:
                errors.append(NotificationErrors.ERR_BAD_NOTIFICATION_TYPE)
        if errors:
            raise serializers.ValidationError(errors)
        return message_uuids


class IntegrationAddSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    server_auth_code = serializers.CharField(required=True, write_only=True)
    user_role = serializers.CharField(required=True)
    integration_type = serializers.CharField(required=True)

    def validate_integration_type(self, integration_type: str) -> str:
        if integration_type != GoogleIntegrationType.GOOGLE_CALENDAR:
            raise serializers.ValidationError(
                GoogleIntegrationErrors.ERR_BAD_INTEGRATION_TYPE
            )
        return integration_type

    def validate_user_role(self, user_role: UserRole) -> UserRole:
        user: User = self.context['user']
        if user_role not in user.role:
            raise serializers.ValidationError(ErrorMessages.ERR_INCORRECT_USER_ROLE)
        return user_role
