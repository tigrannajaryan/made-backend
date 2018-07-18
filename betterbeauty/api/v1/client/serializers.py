from typing import Optional

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.common.fields import PhoneNumberField
from api.common.mixins import FormattedErrorMessageMixin

from api.common.utils import save_profile_photo
from api.v1.client.constants import ErrorMessages
from client.models import Client, ClientOfStylist, PreferredStylist
from core.models import User
from salon.models import Stylist


class ClientProfileSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    phone = PhoneNumberField(read_only=True)
    profile_photo_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    profile_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'profile_photo_id', 'profile_photo_url']

    def create(self, validated_data):
        instance = self.context['user']
        return super(ClientProfileSerializer, self).update(instance, validated_data)

    def save(self, **kwargs):
        profile_photo_id = self.validated_data.pop('profile_photo_id', None)
        user = super(ClientProfileSerializer, self).save(**kwargs)
        if profile_photo_id:
            save_profile_photo(
                user, profile_photo_id
            )
        return user

    def get_profile_photo_url(self, user: User) -> Optional[str]:
        if user.photo:
            return user.photo.url
        return None


class PreferredStylistSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    preference_uuid = serializers.UUIDField(source='uuid')
    uuid = serializers.UUIDField(source='stylist.uuid')
    salon_name = serializers.CharField(
        source='stylist.salon.name', allow_null=True, required=False
    )
    salon_address = serializers.CharField(source='stylist.salon.address', allow_null=True)
    profile_photo_url = serializers.CharField(read_only=True,
                                              source='stylist.get_profile_photo_url')
    first_name = serializers.CharField(source='stylist.user.first_name')
    last_name = serializers.CharField(source='stylist.user.last_name')
    phone = PhoneNumberField(source='stylist.user.phone', )

    class Meta:
        model = PreferredStylist
        fields = ['uuid', 'salon_name', 'salon_address', 'profile_photo_url',
                  'first_name', 'last_name', 'phone', 'preference_uuid']


class ClientPreferredStylistSerializer(serializers.ModelSerializer):

    stylists = PreferredStylistSerializer(source='preferred_stylists', many=True)

    class Meta:
        model = Client
        fields = ['stylists', ]


class AddPreferredClientsSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):
    stylist_uuid = serializers.UUIDField(write_only=True)
    preference_uuid = serializers.UUIDField(read_only=True, source='uuid')

    class Meta:
        model = PreferredStylist
        fields = ['stylist_uuid', 'preference_uuid']

    def validate_stylist_uuid(self, value):
        try:
            stylist: Stylist = Stylist.objects.get(uuid=value)
            client: Client = self.context['user'].client
            PreferredStylist.objects.get(stylist=stylist, client=client, deleted_at=None)
            raise ValidationError(ErrorMessages.ERR_STYLIST_IS_ALREADY_IN_PREFERENCE)
        except Stylist.DoesNotExist:
            raise ValidationError(ErrorMessages.ERR_INVALID_STYLIST_UUID)
        except PreferredStylist.DoesNotExist:
            return value

    def to_internal_value(self, data):
        data = super(AddPreferredClientsSerializer, self).to_internal_value(data)
        stylist: Stylist = Stylist.objects.get(uuid=data['stylist_uuid'])
        data['stylist'] = stylist
        return data

    def save(self, **kwargs):
        stylist_uuid = self.validated_data['stylist_uuid']
        stylist: Stylist = Stylist.objects.get(uuid=stylist_uuid)
        client: Client = self.context['user'].client
        with transaction.atomic():
            preferred_stylist, created = PreferredStylist.all_objects.update_or_create(
                stylist=stylist, client=client, defaults={
                    'deleted_at': None
                })
            self.instance = preferred_stylist
            return self.instance


class ClientOfStylistSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):
    uuid = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    phone = PhoneNumberField(source='user.phone')

    class Meta:
        model = ClientOfStylist
        fields = ['first_name', 'last_name', 'phone', 'uuid', ]
