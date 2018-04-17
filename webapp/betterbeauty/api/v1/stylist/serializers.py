from rest_framework import serializers

from django.db import transaction

from core.models import User
from salon.models import Salon, Stylist, StylistService, StylistServicePhotoSample


class StylistUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', ]


class SalonSerializer(serializers.ModelSerializer):
    profile_photo_url = serializers.CharField(source='get_photo_url', read_only=True)
    full_address = serializers.CharField(source='get_full_address', read_only=True)

    class Meta:
        model = Salon
        fields = [
            'name', 'address', 'city', 'zip_code', 'state', 'full_address', 'profile_photo_url',
        ]


class StylistServicePhotoSampleSerializer(serializers.ModelSerializer):
    url = serializers.CharField(read_only=True, source='photo.url')

    class Meta:
        model = StylistServicePhotoSample
        fields = ['url', ]


class StylistServiceSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.SerializerMethodField()
    photo_samples = StylistServicePhotoSampleSerializer(many=True)

    class Meta:
        model = StylistService
        fields = [
            'id', 'name', 'description', 'base_price', 'duration_minutes',
            'is_enabled', 'photo_samples',
        ]

    def get_duration_minutes(self, obj: StylistService) -> int:
        return int(obj.duration.total_seconds() / 60)


class StylistSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    salon_name = serializers.CharField(source='salon.name')
    salon_address = serializers.CharField(source='salon.address')

    # TODO: Enable address sub-fields as soon as we have proper address splitting mechanics

    # salon_city = serializers.CharField(source='salon.city', required=False)
    # salon_zipcode = serializers.CharField(source='salon.zip_code', required=False)
    # salon_state = serializers.CharField(source='salon.state', required=False)

    salon_photo_url = serializers.CharField(read_only=True, source='salon.get_photo_url')

    profile_photo_url = serializers.CharField(read_only=True, source='get_profile_photo_url')

    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    phone = serializers.CharField(source='user.phone')

    class Meta:
        model = Stylist
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'profile_photo_url', 'salon_photo_url',
            'salon_name', 'salon_address',
        ]

    def update(self, stylist: Stylist, validated_data) -> Stylist:
        with transaction.atomic():
            user_data = validated_data.pop('user', {})
            if user_data:
                user_serializer = StylistUserSerializer(
                    instance=stylist.user, data=user_data, partial=True
                )
                if user_serializer.is_valid(raise_exception=True):
                    user_serializer.save()

            salon_data = validated_data.pop('salon', {})
            if salon_data:
                salon_serializer = SalonSerializer(
                    instance=stylist.salon, data=salon_data, partial=True
                )
                if salon_serializer.is_valid(raise_exception=True):
                    salon_serializer.save()
        return super(StylistSerializer, self).update(stylist, validated_data)

    def create(self, validated_data) -> Stylist:
        user = self.context['user']

        if user and user.is_stylist():
            return self.update(user.stylist, validated_data)

        with transaction.atomic():
            user_data = validated_data.pop('user', {})
            if user_data:
                user_serializer = StylistUserSerializer(
                    instance=user, data=user_data
                )
                if user_serializer.is_valid(raise_exception=True):
                    user = user_serializer.save()

            salon_data = validated_data.pop('salon', {})
            salon_serializer = SalonSerializer(
                data=salon_data
            )
            salon_serializer.is_valid(raise_exception=True)
            salon = salon_serializer.save()

            validated_data.update(
                {
                    'salon': salon,
                    'user': user,
                }
            )
            return super(StylistSerializer, self).create(validated_data)
