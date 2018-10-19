from datetime import timedelta

from django.utils import timezone

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework_jwt.serializers import (
    RefreshJSONWebTokenSerializer,
)

from api.common.fields import PhoneNumberField
from api.common.mixins import FormattedErrorMessageMixin
from api.v1.stylist.serializers import (
    StylistProfileStatusSerializer,
    StylistSerializer,
    StylistSerializerWithInvitation
)
from client.constants import MINUTES_BEFORE_REQUESTING_NEW_CODE
from core.choices import USER_ROLE
from core.models import PhoneSMSCodes
from core.types import UserRole
from salon.models import Invitation
from salon.types import InvitationStatus

from .constants import ErrorMessages


class AuthMessageTranslationMixin(object):
    def validate(self, attrs):
        try:
            attrs = super(AuthMessageTranslationMixin, self).validate(attrs)
        except serializers.ValidationError as err:
            details = err.detail
            translated_details = [self.configured_messages.get(d) for d in details]
            raise ValidationError(translated_details)
        return attrs


class CustomRefreshJSONWebTokenSerializer(
    AuthMessageTranslationMixin,
    FormattedErrorMessageMixin,
    RefreshJSONWebTokenSerializer
):
    configured_messages = {
        'Refresh has expired.': ErrorMessages.ERR_REFRESH_HAS_EXPIRED,
        'orig_iat field is required.': ErrorMessages.ERR_ORIG_IAT_IS_REQUIRED
    }


class AuthTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)
    profile = serializers.SerializerMethodField()
    profile_status = serializers.SerializerMethodField()
    role = serializers.ChoiceField(read_only=True, choices=USER_ROLE)

    def get_profile(self, data):
        user = self.context['user']
        if user.is_stylist():
            return StylistSerializer(getattr(user, 'stylist', None)).data
        return []

    def get_profile_status(self, data):
        user = self.context['user']
        if user.is_stylist():
            return StylistProfileStatusSerializer(getattr(user, 'stylist', None)).data
        return []


class ClientAuthTokenSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    token = serializers.CharField(read_only=True)
    created_at = serializers.IntegerField(read_only=True)
    role = serializers.ChoiceField(read_only=True, choices=USER_ROLE)
    stylist_invitation = serializers.SerializerMethodField()

    def get_stylist_invitation(self, data):
        user = self.context['user']
        if user.is_client():
            invitations = Invitation.objects.filter(
                phone=user.phone).exclude(
                status=InvitationStatus.ACCEPTED).order_by('-created_at')[:5]
            return StylistSerializerWithInvitation(invitations, many=True).data


class PhoneSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    phone = PhoneNumberField()
    role = serializers.ChoiceField(choices=USER_ROLE, default=UserRole.CLIENT.value)

    def validate(self, attrs):
        """
            If the existing code is generated in less than 'MINUTES_BEFORE_REQUESTING_NEW_CODE'
            minutes, we raise validation error,
        """
        phone = attrs['phone']
        role = attrs.get('role', UserRole.CLIENT.value)
        try:
            phone_sms_code = PhoneSMSCodes.objects.get(phone=phone, role=role)
            if not (timezone.now() - phone_sms_code.generated_at) > timedelta(
                    minutes=MINUTES_BEFORE_REQUESTING_NEW_CODE):
                raise ValidationError(ErrorMessages.ERR_WAIT_TO_REREQUEST_NEW_CODE)
            return attrs
        except PhoneSMSCodes.DoesNotExist:
            return attrs


class PhoneSMSCodeSerializer(FormattedErrorMessageMixin, serializers.Serializer):

    phone = PhoneNumberField()
    code = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(
        required=False, choices=USER_ROLE, default=UserRole.CLIENT.value
    )

    def validate(self, attrs):
        data = self.initial_data
        role = data.get('role', UserRole.CLIENT)
        is_valid_code: bool = PhoneSMSCodes.validate_sms_code(
            phone=data['phone'], code=data['code'], role=role)
        if not is_valid_code:
            raise ValidationError({
                'code': ErrorMessages.ERR_INVALID_SMS_CODE
            })
        return attrs

    class Meta:
        model = PhoneSMSCodes
        fields = ['phone', 'code', 'role', ]
