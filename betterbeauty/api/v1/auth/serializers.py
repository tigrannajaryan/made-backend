from django.db import transaction

from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework_jwt.serializers import (
    JSONWebTokenSerializer,
    RefreshJSONWebTokenSerializer,
)

from api.common.fields import PhoneNumberField
from api.common.mixins import FormattedErrorMessageMixin
from api.v1.stylist.serializers import StylistProfileStatusSerializer, StylistSerializer
from client.models import PhoneSMSCodes
from core.choices import USER_ROLE
from core.models import User
from core.types import FBAccessToken, FBUserID, UserRole
from core.utils.facebook import get_or_create_facebook_user
from salon.models import Stylist
from salon.types import InvitationStatus
from salon.utils import create_stylist_profile_for_user

from .constants import ErrorMessages, ROLES_WITH_ALLOWED_LOGIN


class AuthMessageTranslationMixin(object):
    def validate(self, attrs):
        try:
            attrs = super(AuthMessageTranslationMixin, self).validate(attrs)
        except serializers.ValidationError as err:
            details = err.detail
            translated_details = [self.configured_messages.get(d) for d in details]
            raise ValidationError(translated_details)
        return attrs


class CustomJSONWebTokenSerializer(
    AuthMessageTranslationMixin,
    FormattedErrorMessageMixin,
    JSONWebTokenSerializer
):
    configured_messages = {
        'User account is disabled.': ErrorMessages.ERR_ACCOUNT_DISABLED,
        'Unable to log in with provided credentials.':
            ErrorMessages.ERR_UNABLE_TO_LOGIN_WITH_CREDENTIALS,
        'Must include "email" and "password".':
            ErrorMessages.ERR_MUST_INCLUDE_EMAIL_AND_PASSWORD
    }


class CustomRefreshJSONWebTokenSerializer(
    AuthMessageTranslationMixin,
    FormattedErrorMessageMixin,
    RefreshJSONWebTokenSerializer
):
    configured_messages = {
        'Refresh has expired.': ErrorMessages.ERR_REFRESH_HAS_EXPIRED,
        'orig_iat field is required.': ErrorMessages.ERR_ORIG_IAT_IS_REQUIRED
    }


class CreateProfileMixin(object):
    def create_profile_for_user(self, user: User, role: UserRole) -> None:
        assert role in ROLES_WITH_ALLOWED_LOGIN
        if role == UserRole.STYLIST:
            create_stylist_profile_for_user(user=user)
        # TODO: Implement creating a client profile similar to stylist


class UserRegistrationSerializer(
    FormattedErrorMessageMixin,
    CreateProfileMixin,
    serializers.Serializer
):
    email = serializers.EmailField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)
    role = serializers.ChoiceField(required=True, write_only=True, choices=USER_ROLE)

    def clear_email(self, email: str) -> str:
        return email.lower().strip()

    def validate_email(self, email: str):
        if User.objects.filter(email__iexact=email.strip()).exists():
            raise ValidationError(
                ErrorMessages.ERR_EMAIL_ALREADY_TAKEN
            )
        return email

    def validate_role(self, role: UserRole) -> UserRole:
        if role not in ROLES_WITH_ALLOWED_LOGIN:
            raise ValidationError(ErrorMessages.ERR_INCORRECT_USER_ROLE)
        return role

    def save(self, **kwargs) -> User:
        email = self.validated_data['email']
        password = self.validated_data['password']
        role = self.validated_data['role']
        with transaction.atomic():
            user = User.objects.create_user(email=email, password=password, role=[role])
            self.create_profile_for_user(user=user, role=role)
        return user


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
            stylists = Stylist.objects.filter(
                invites__phone=user.phone).exclude(invites__status=InvitationStatus.ACCEPTED)
            return StylistSerializer(stylists, many=True).data


class FacebookAuthTokenSerializer(
    FormattedErrorMessageMixin,
    CreateProfileMixin,
    serializers.Serializer
):
    fb_access_token = serializers.CharField(required=True)
    fb_user_id = serializers.CharField(required=True)
    role = serializers.ChoiceField(required=True, write_only=True, choices=USER_ROLE)

    def to_internal_value(self, data):
        return {
            'fb_access_token': data['fbAccessToken'],
            'fb_user_id': data['fbUserID'],
            'role': data['role']
        }

    def validate_role(self, role: UserRole) -> UserRole:
        if role not in ROLES_WITH_ALLOWED_LOGIN:
            raise ValidationError(ErrorMessages.ERR_INCORRECT_USER_ROLE)
        return role

    def save(self, **kwargs) -> User:
        fb_user_id: FBUserID = self.validated_data['fb_user_id']
        fb_access_token: FBAccessToken = self.validated_data['fb_access_token']
        role: UserRole = self.validated_data['role']
        with transaction.atomic():
            user, created = get_or_create_facebook_user(
                fb_access_token, fb_user_id, role
            )
            if created:
                self.create_profile_for_user(user=user, role=role)
            return user


class PhoneSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    phone = PhoneNumberField()


class PhoneSMSCodeSerializer(FormattedErrorMessageMixin, serializers.Serializer):

    phone = PhoneNumberField()
    code = serializers.CharField(write_only=True)

    class Meta:
        model = PhoneSMSCodes
        fields = ['phone', 'code']
