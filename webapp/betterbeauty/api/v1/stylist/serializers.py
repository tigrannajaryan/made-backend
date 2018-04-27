from typing import Optional

from rest_framework import serializers

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.shortcuts import get_object_or_404

from core.models import TemporaryFile, User
from salon.models import (
    Salon,
    ServiceCategory,
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


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ['name', 'uuid', ]


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
    category_uuid = serializers.UUIDField(source='category.uuid')
    category_name = serializers.CharField(source='category.name', read_only=True)

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

        category_data = data_to_save.pop('category', {})
        category_uuid = category_data.get('uuid', None)
        category = get_object_or_404(ServiceCategory, uuid=category_uuid)

        data_to_save.update({'category': category})
        try:
            service = stylist.services.get(pk=pk)
            return self.update(service, data_to_save)
        except StylistService.DoesNotExist:
            return StylistService.objects.create(**data_to_save)

    class Meta:
        model = StylistService
        fields = [
            'id', 'name', 'description', 'base_price', 'duration_minutes',
            'is_enabled', 'photo_samples', 'category_uuid', 'category_name',
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
        fields = ['id', 'name', 'description', 'base_price', 'duration_minutes', ]


class ServiceTemplateSetListSerializer(serializers.ModelSerializer):
    services = serializers.SerializerMethodField()
    image_url = serializers.CharField(read_only=True, source='get_image_url')

    class Meta:
        model = ServiceTemplateSet
        fields = ['uuid', 'name', 'description', 'services', 'image_url', ]

    def get_services(self, template_set: ServiceTemplateSet):
        templates = template_set.templates.all()[:MAX_SERVICE_TEMPLATE_PREVIEW_COUNT]
        return ServiceTemplateSerializer(templates, many=True).data


class ServiceCategoryDetailsSerializer(serializers.ModelSerializer):

    services = serializers.SerializerMethodField()

    class Meta:
        model = ServiceCategory
        fields = ['name', 'uuid', 'services']

    def get_services(self, service_category: ServiceCategory):
        templates = service_category.templates.order_by('-base_price')
        if 'service_template_set' in self.context:
            templates = templates.filter(templateset=self.context['service_template_set'])
        return ServiceTemplateDetailsSerializer(templates, many=True).data


class ServiceTemplateSetDetailsSerializer(serializers.ModelSerializer):
    categories = serializers.SerializerMethodField()
    image_url = serializers.CharField(read_only=True, source='get_image_url')

    class Meta:
        model = ServiceTemplateSet
        fields = ['id', 'name', 'description', 'categories', 'image_url']

    def get_categories(self, service_template_set: ServiceTemplateSet):
        category_queryset = ServiceCategory.objects.all().order_by(
            'name', 'uuid'
        ).distinct('name', 'uuid')
        return ServiceCategoryDetailsSerializer(
            category_queryset,
            context={'service_template_set': service_template_set},
            many=True
        ).data


class StylistServiceListSerializer(serializers.Serializer):
    """Serves for convenience of packing services under dictionary key"""
    services = StylistServiceSerializer(many=True)


class StylistProfileStatusSerializer(serializers.ModelSerializer):
    has_personal_data = serializers.SerializerMethodField()
    has_picture_set = serializers.SerializerMethodField()
    has_services_set = serializers.SerializerMethodField()
    has_business_hours_set = serializers.SerializerMethodField()
    has_weekday_discounts_set = serializers.SerializerMethodField()
    has_other_discounts_set = serializers.SerializerMethodField()
    has_invited_clients = serializers.SerializerMethodField()

    class Meta:
        model = Stylist
        fields = [
            'has_personal_data', 'has_picture_set', 'has_services_set',
            'has_business_hours_set', 'has_weekday_discounts_set', 'has_other_discounts_set',
            'has_invited_clients',
        ]

    def get_has_personal_data(self, stylist: Stylist) -> bool:
        full_name = stylist.get_full_name()
        has_name = full_name and len(full_name) > 1
        salon: Optional[Salon] = getattr(stylist, 'salon')
        has_address = salon and salon.address
        return bool(has_name and stylist.user.phone and has_address)

    def get_has_picture_set(self, stylist: Stylist) -> bool:
        return stylist.get_profile_photo_url() is not None

    def get_has_services_set(self, stylist: Stylist) -> bool:
        return stylist.services.exists()

    def get_has_business_hours_set(self, stylist: Stylist) -> bool:
        return stylist.available_days.exists()

    def get_has_weekday_discounts_set(self, stylist: Stylist) -> bool:
        return stylist.weekday_discounts.exists()

    def get_has_other_discounts_set(self, stylist: Stylist) -> bool:
        """Returns True if any of the miscellaneous discounts is set"""
        return any([
            hasattr(stylist, 'early_rebook_discount'),
            hasattr(stylist, 'first_time_book_discount'),
            stylist.date_range_discounts.exists()
        ])

    def get_has_invited_clients(self, stylist: Stylist) -> bool:
        # We don't have model for this right now, so set to False
        # TODO: reflect actual state
        return False
