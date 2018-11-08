from django.conf import settings

from rest_framework import serializers

from api.common.mixins import FormattedErrorMessageMixin
from api.v1.auth.constants import ErrorMessages
from core.models import TemporaryFile, User
from core.types import UserRole
from integrations.push.types import PUSH_NOTIFICATION_TOKEN_CHOICES


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
