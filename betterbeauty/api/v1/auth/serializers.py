from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.v1.auth.constants import ROLES_WITH_ALLOWED_LOGIN
from api.v1.stylist.serializers import StylistProfileStatusSerializer, StylistSerializer
from client.models import PhoneSMSCodes
from core.choices import USER_ROLE
from core.models import User
from core.types import FBAccessToken, FBUserID, UserRole
from core.utils.facebook import get_or_create_facebook_user
from salon.models import Stylist
from salon.types import InvitationStatus
from salon.utils import create_stylist_profile_for_user


class CreateProfileMixin(object):
    def create_profile_for_user(self, user: User, role: UserRole) -> None:
        assert role in ROLES_WITH_ALLOWED_LOGIN
        if role == UserRole.STYLIST:
            create_stylist_profile_for_user(user=user)
        # TODO: Implement creating a client profile similar to stylist


class UserRegistrationSerializer(CreateProfileMixin, serializers.Serializer):
    email = serializers.EmailField(required=True, write_only=True)
    password = serializers.CharField(required=True, write_only=True)
    role = serializers.ChoiceField(required=True, write_only=True, choices=USER_ROLE)

    def clear_email(self, email: str) -> str:
        return email.lower().strip()

    def validate_email(self, email: str):
        if User.objects.filter(email__iexact=email.strip()).exists():
            raise ValidationError(_(
                'This email is already taken'
            ))
        return email

    def validate_role(self, role: UserRole) -> UserRole:
        if role not in ROLES_WITH_ALLOWED_LOGIN:
            raise ValidationError('Incorrect user role')
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


class ClientAuthTokenSerializer(serializers.Serializer):
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


class FacebookAuthTokenSerializer(CreateProfileMixin, serializers.Serializer):
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
            raise ValidationError('Incorrect user role')
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


class PhoneSerializer(serializers.Serializer):
    phone = serializers.CharField()


class PhoneSMSCodeSerializer(serializers.Serializer):

    phone = serializers.CharField()
    code = serializers.CharField(write_only=True)

    class Meta:
        model = PhoneSMSCodes
        fields = ['phone', 'code']
