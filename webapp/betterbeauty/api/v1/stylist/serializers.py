from typing import Optional

from rest_framework import serializers

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.shortcuts import get_object_or_404

from core.models import TemporaryFile, User
from salon.models import (
    Salon,
    ServiceTemplate,
    ServiceTemplateSet,
    Stylist,
    StylistService,
    StylistServicePhotoSample,
)
from .constants import MAX_SERVICE_TEMPLATE_PREVIEW_COUNT
from .fields import DurationMinuteField


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
    id = serializers.IntegerField(required=False)
    duration_minutes = DurationMinuteField(source='duration')
    photo_samples = StylistServicePhotoSampleSerializer(
        many=True, read_only=True)
    base_price = serializers.DecimalField(
        coerce_to_string=False, max_digits=6, decimal_places=2
    )

    def validate_id(self, pk: Optional[int]) -> Optional[int]:
        if pk is not None:
            stylist = self.context['stylist']
            if not stylist.services.filter(pk=pk).exists():
                raise serializers.ValidationError(
                    'Stylist does not have service with id == {0}'.format(pk)
                )
        return pk

    def create(self, validated_data):
        stylist = self.context['stylist']
        data_to_save = validated_data.copy()
        data_to_save.update({'stylist': stylist})
        pk = data_to_save.pop('id', None)
        try:
            service = stylist.services.get(pk=pk)
            return self.update(service, data_to_save)
        except StylistService.DoesNotExist:
            return StylistService.objects.create(**data_to_save)

    class Meta:
        model = StylistService
        fields = [
            'id', 'name', 'description', 'base_price', 'duration_minutes',
            'is_enabled', 'photo_samples',
        ]


class StylistSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)

    salon_name = serializers.CharField(source='salon.name', allow_null=True)
    salon_address = serializers.CharField(source='salon.address', allow_null=True)

    # TODO: Enable address sub-fields as soon as we have proper address splitting mechanics

    # salon_city = serializers.CharField(source='salon.city', required=False)
    # salon_zipcode = serializers.CharField(source='salon.zip_code', required=False)
    # salon_state = serializers.CharField(source='salon.state', required=False)

    profile_photo_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    profile_photo_url = serializers.CharField(read_only=True, source='get_profile_photo_url')

    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    phone = serializers.CharField(source='user.phone')

    class Meta:
        model = Stylist
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'profile_photo_url',
            'salon_name', 'salon_address', 'profile_photo_id',
        ]

    def validate_salon_name(self, salon_name: str) -> str:
        if not salon_name:
            raise serializers.ValidationError('This field is required')
        return salon_name

    def validate_salon_address(self, salon_address: str) -> str:
        if not salon_address:
            raise serializers.ValidationError('This field is required')
        return salon_address

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
            self._save_profile_photo(
                stylist.user, validated_data.get('profile_photo_id', None)
            )
        return super(StylistSerializer, self).update(stylist, validated_data)

    def create(self, validated_data) -> Stylist:
        user: User = self.context['user']

        if user and hasattr(user, 'stylist'):
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
            profile_photo_id = validated_data.pop('profile_photo_id', None)
            stylist = super(StylistSerializer, self).create(validated_data)
            self._save_profile_photo(
                user, profile_photo_id
            )
            return stylist

    def _save_profile_photo(
            self, user: Optional[User], photo_uuid: Optional[str]
    ) -> None:
        if not user or not photo_uuid:
            return

        image_file_record: TemporaryFile = get_object_or_404(
            TemporaryFile,
            uuid=photo_uuid,
            uploaded_by=user
        )
        content_file = ContentFile(image_file_record.file.read())
        target_file_name = image_file_record.file.name
        user.photo.save(
            default_storage.get_available_name(target_file_name), content_file
        )
        image_file_record.file.close()


class ServiceTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceTemplate
        fields = ['name', ]


class ServiceTemplateDetailsSerializer(serializers.ModelSerializer):
    duration_minutes = DurationMinuteField(source='duration')
    base_price = serializers.DecimalField(
        coerce_to_string=False, max_digits=6, decimal_places=2)

    class Meta:
        model = ServiceTemplate
        fields = ['name', 'description', 'base_price', 'duration_minutes', ]


class ServiceTemplateSetListSerializer(serializers.ModelSerializer):
    templates = serializers.SerializerMethodField()

    class Meta:
        model = ServiceTemplateSet
        fields = ['id', 'name', 'description', 'templates', ]

    def get_templates(self, template_set: ServiceTemplateSet):
        templates = template_set.templates.all()[:MAX_SERVICE_TEMPLATE_PREVIEW_COUNT]
        return ServiceTemplateSerializer(templates, many=True).data


class ServiceTemplateSetDetailsSerializer(serializers.ModelSerializer):
    templates = ServiceTemplateDetailsSerializer(many=True)

    class Meta:
        model = ServiceTemplateSet
        fields = ['id', 'name', 'description', 'templates', ]


class StylistServiceListSerializer(serializers.Serializer):
    """Serves for convenience of packing services under dictionary key"""
    services = StylistServiceSerializer(many=True)
