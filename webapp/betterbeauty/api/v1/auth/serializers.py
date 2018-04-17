from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from django.utils.translation import ugettext_lazy as _

from api.v1.stylist.serializers import StylistSerializer
from core.models import User


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

        user = User.objects.create_user(email=email, password=password)
        return user


class AuthTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    expires_in = serializers.IntegerField(read_only=True)
    stylist = StylistSerializer(allow_null=True)
