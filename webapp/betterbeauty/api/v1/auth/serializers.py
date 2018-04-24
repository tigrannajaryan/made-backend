from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django.db import transaction
from django.utils.translation import ugettext_lazy as _

from api.v1.stylist.serializers import StylistSerializer, StylistProfileStatusSerializer
from core.choices import USER_ROLE
from core.models import User
from core.types import FBAccessToken, FBUserID
from core.utils.facebook import get_or_create_facebook_user
from salon.models import Stylist


class UserRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)

    def clear_email(self, email: str) -> str:
        return email.lower().strip()

    def validate_email(self, email: str):
        if User.objects.filter(email__iexact=email.strip()).exists():
            raise ValidationError(_(
                'This email is already taken'
            ))
        return email

    def save(self, **kwargs) -> User:
        email = self.validated_data['email']
        password = self.validated_data['password']

        user = User.objects.create_user(email=email, password=password, role=USER_ROLE.stylist)
        return user


class AuthTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)
    stylist = StylistSerializer(allow_null=True)
    stylist_profile_status = StylistProfileStatusSerializer(
        allow_null=True, read_only=True
    )


class FacebookAuthTokenSerializer(serializers.Serializer):
    fb_access_token = serializers.CharField(required=True)
    fb_user_id = serializers.CharField(required=True)

    def to_internal_value(self, data):
        return {
            'fb_access_token': data['fbAccessToken'],
            'fb_user_id': data['fbUserID'],
        }

    def save(self, **kwargs) -> User:
        fb_user_id: FBUserID = self.validated_data['fb_user_id']
        fb_access_token: FBAccessToken = self.validated_data['fb_access_token']
        with transaction.atomic():
            user, created = get_or_create_facebook_user(
                fb_access_token, fb_user_id
            )
            if created:
                Stylist.objects.create(user=user)
            return user
