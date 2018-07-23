import datetime
from decimal import Decimal
from typing import Optional, List, Tuple

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.common.fields import PhoneNumberField
from api.common.mixins import FormattedErrorMessageMixin

from api.common.utils import save_profile_photo
from api.v1.client.constants import ErrorMessages

from api.v1.stylist.serializers import (
    StylistServiceCategoryDetailsSerializer)

from api.v1.stylist.fields import DurationMinuteField
from appointment.models import AppointmentService, Appointment
from client.models import Client, ClientOfStylist, PreferredStylist
from core.models import User
from core.types import AppointmentPrices
from core.utils import calculate_appointment_prices
from pricing import CalculatedPrice
from salon.models import ServiceCategory, Stylist, StylistService
from salon.utils import calculate_price_and_discount_for_client_on_date


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


class StylistServiceListSerializer(serializers.ModelSerializer):
    stylist_uuid = serializers.UUIDField(read_only=True, source='uuid')
    categories = serializers.SerializerMethodField(read_only=True)

    class Meta:
        fields = ['stylist_uuid', 'categories']
        model = Stylist

    def get_categories(self, stylist: Stylist):
        category_queryset = ServiceCategory.objects.all().order_by(
            'name', 'uuid'
        ).distinct('name', 'uuid')
        return StylistServiceCategoryDetailsSerializer(
            category_queryset,
            context={'stylist': stylist},
            many=True
        ).data


class ServicePricingRequestSerializer(serializers.Serializer):
    service_uuid = serializers.UUIDField()


class AppointmentServiceSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    uuid = serializers.UUIDField(read_only=True)
    service_name = serializers.CharField(read_only=True)
    regular_price = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )
    client_price = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, required=False
    )

    class Meta:
        model = AppointmentService
        fields = [
            'uuid', 'service_name', 'service_uuid', 'client_price', 'regular_price',
            'is_original',
        ]


class AppointmentSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    uuid = serializers.UUIDField(read_only=True)
    stylist_uuid = serializers.UUIDField(required=True, source='stylist.uuid')
    datetime_start_at = serializers.DateTimeField()
    services = AppointmentServiceSerializer(many=True)
    stylist_first_name = serializers.CharField(read_only=True, source='stylist.first_name')
    stylist_last_name = serializers.CharField(read_only=True, source='stylist.last_name')
    stylist_phone = serializers.CharField(read_only=True, source='stylist.phone')

    total_client_price_before_tax = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )
    total_tax = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )
    total_card_fee = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )

    grand_total = serializers.DecimalField(
        max_digits=4, decimal_places=0, coerce_to_string=False, read_only=True
    )
    has_tax_included = serializers.NullBooleanField(read_only=True)
    has_card_fee_included = serializers.NullBooleanField(read_only=True)
    duration_minutes = DurationMinuteField(source='duration', read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'uuid', 'stylist_uuid', 'stylist_first_name', 'stylist_last_name',
            'stylist_phone', 'datetime_start_at', 'duration_minutes', 'status',
            'total_tax', 'total_card_fee', 'total_client_price_before_tax',
            'services', 'grand_total', 'has_tax_included', 'has_card_fee_included',
        ]

    def create(self, validated_data):

        data = validated_data.copy()
        stylist_data = validated_data.pop('stylist', {})
        stylist_uuid = stylist_data.get('uuid', None)

        stylist: Stylist = Stylist.objects.get(uuid=stylist_uuid)

        appointment_services = data.pop('services', [])
        datetime_start_at: datetime.datetime = data['datetime_start_at']

        client: Client = self.context['user'].client

        with transaction.atomic():
            client_of_stylist, created = ClientOfStylist.objects.get_or_create(stylist=stylist, client=client)

            data['client'] = client_of_stylist
            data['stylist'] = stylist
            data['created_by'] = client.user

            services_with_client_prices: List[Tuple[StylistService, CalculatedPrice]] = []
            for appointment_service in appointment_services:
                service: StylistService = stylist.services.get(
                    uuid=appointment_service['service_uuid']
                )
                client_price: CalculatedPrice = calculate_price_and_discount_for_client_on_date(
                    service=service, client=client_of_stylist, date=datetime_start_at.date()
                )
                services_with_client_prices.append((service, client_price))
            appointment: Appointment = super(AppointmentSerializer, self).create(data)
            total_client_price_before_tax: Decimal = 0
            for (service, client_price) in services_with_client_prices:
                AppointmentService.objects.create(
                    appointment=appointment,
                    service_name=service.name,
                    service_uuid=service.uuid,
                    duration=service.duration,
                    regular_price=service.regular_price,
                    client_price=client_price.price,
                    calculated_price=client_price.price,
                    applied_discount=(
                        client_price.applied_discount.value
                        if client_price.applied_discount else None
                    ),
                    discount_percentage=client_price.discount_percentage,
                    is_price_edited=False,
                    is_original=True
                )
                total_client_price_before_tax += Decimal(client_price.price)

            # set initial price settings
            appointment_prices: AppointmentPrices = calculate_appointment_prices(
                price_before_tax=total_client_price_before_tax,
                include_card_fee=False, include_tax=False
            )
            for k, v in appointment_prices._asdict().items():
                setattr(appointment, k, v)
            appointment.save()
            appointment.append_status_history(updated_by=stylist.user)

        return appointment
