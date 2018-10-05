import datetime
import uuid
from decimal import Decimal
from math import trunc
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.common.fields import PhoneNumberField
from api.common.mixins import FormattedErrorMessageMixin

from api.common.utils import save_profile_photo
from api.v1.client.constants import ErrorMessages

from api.v1.stylist.fields import DurationMinuteField
from api.v1.stylist.serializers import (
    AppointmentServiceSerializer,
    StylistServiceCategoryDetailsSerializer,
    StylistServicePriceSerializer
)

from appointment.constants import (
    APPOINTMENT_CLIENT_SETTABLE_STATUSES,
    DEFAULT_HAS_CARD_FEE_INCLUDED, DEFAULT_HAS_TAX_INCLUDED, ErrorMessages as appointment_errors)
from appointment.models import Appointment, AppointmentService
from appointment.types import AppointmentStatus
from client.constants import END_OF_DAY_BUFFER_TIME_IN_MINUTES
from client.models import Client, ClientOfStylist, PreferredStylist
from core.models import User
from core.types import AppointmentPrices
from core.utils import calculate_appointment_prices
from pricing import CalculatedPrice
from salon.models import Invitation, ServiceCategory, Stylist, StylistService
from salon.types import InvitationStatus, PriceOnDate
from salon.utils import (
    calculate_price_and_discount_for_client_on_date,
    generate_prices_for_stylist_service
)


class ClientProfileSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    phone = PhoneNumberField(read_only=True)
    profile_photo_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    profile_photo_url = serializers.CharField(read_only=True,
                                              source='client.get_profile_photo_url', default=None)
    birthday = serializers.DateField(source='client.birthday', required=False, )
    zip_code = serializers.CharField(source='client.zip_code',
                                     required=False, allow_blank=True, allow_null=True)
    email = serializers.CharField(source='client.email',
                                  required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(source='client.city', read_only=True)
    state = serializers.CharField(source='client.state', read_only=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone', 'profile_photo_id',
                  'profile_photo_url', 'zip_code', 'birthday', 'email', 'city', 'state']

    def validate_email(self, email: str):
        if email and self.instance and Client.objects.exclude(
                pk=self.instance.client.pk).filter(email=email):
            raise serializers.ValidationError(ErrorMessages.ERR_UNIQUE_CLIENT_EMAIL)
        return email

    def create(self, validated_data):
        instance = self.context['user']
        return super(ClientProfileSerializer, self).update(instance, validated_data)

    @transaction.atomic
    def save(self, **kwargs):
        should_save_photo = False
        profile_photo_id = None
        if 'profile_photo_id' in self.validated_data:
            should_save_photo = True
            profile_photo_id = self.validated_data.pop('profile_photo_id')
        client_data = self.validated_data.pop('client', None)
        client = self.context['user'].client
        if client_data:
            if client.zip_code != client_data.get('zip_code', client.zip_code):
                client.zip_code = client_data.get('zip_code', client.zip_code)
                client.last_geo_coded = None
            client.birthday = client_data.get('birthday', client.birthday)
            client.email = client_data.get('email', client.email)
            client.save(update_fields=['zip_code', 'birthday', 'email', 'last_geo_coded'])
        user = super(ClientProfileSerializer, self).save(**kwargs)
        if should_save_photo:
            save_profile_photo(
                user, profile_photo_id
            )
        return user


class PreferredStylistSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    preference_uuid = serializers.UUIDField(source='uuid')
    uuid = serializers.UUIDField(source='stylist.uuid')
    salon_name = serializers.CharField(
        source='stylist.salon.name', allow_null=True, required=False
    )
    instagram_url = serializers.CharField(
        source="stylist.instagram_url", read_only=True
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
                  'first_name', 'last_name', 'phone', 'preference_uuid', 'instagram_url']


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
            client_of_stylist, created = ClientOfStylist.objects.get_or_create(
                client=client, stylist=stylist, defaults={
                    'first_name': client.user.first_name,
                    'last_name': client.user.last_name,
                    'phone': client.user.phone
                })
            Invitation.objects.filter(phone=client.user.phone, stylist=stylist,
                                      status=InvitationStatus.INVITED).update(
                status=InvitationStatus.ACCEPTED, accepted_at=timezone.now(),
                created_client=client_of_stylist)
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


class StylistServiceListSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):
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


class ServicePricingRequestSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    service_uuids = serializers.ListField(child=serializers.UUIDField())

    def validate_service_uuids(self, service_uuids: List[str]):
        context: Dict = self.context
        client: Client = context['client']
        available_services = StylistService.objects.filter(
            Q(
                stylist__preferredstylist__client=client,
                stylist__preferredstylist__deleted_at__isnull=True
            ) | Q(
                stylist__clients_of_stylist__client=client
            )
        ).values_list('uuid', flat=True)
        if not all(x in available_services for x in service_uuids):
            raise serializers.ValidationError(
                appointment_errors.ERR_SERVICE_DOES_NOT_EXIST
            )
        return service_uuids


class ServicePricingSerializer(serializers.Serializer):
    service_uuids = serializers.ListField(child=serializers.UUIDField())
    stylist_uuid = serializers.UUIDField(read_only=True)
    prices = serializers.SerializerMethodField(read_only=True)

    class Meta:
        fields = ['service_uuid', 'service_name', 'prices', ]

    def get_prices(self, object):
        services = self.context.get('services', [])
        client_of_stylist: ClientOfStylist = self.context['client_of_stylist']
        stylist = self.context['stylist']
        prices_and_dates: Iterable[PriceOnDate] = generate_prices_for_stylist_service(
            services,
            client_of_stylist,
            exclude_fully_booked=False,
            exclude_unavailable_days=False
        )
        prices_and_dates_list = []
        for obj in prices_and_dates:
            availability_on_day = stylist.available_days.filter(
                weekday=obj.date.isoweekday(),
                is_available=True).last() if obj.date == stylist.get_current_now().date() else None
            stylist_eod = datetime.datetime.combine(date=obj.date,
                                                    time=availability_on_day.work_end_at,
                                                    tzinfo=stylist.salon.timezone
                                                    ) if availability_on_day else None
            if not stylist_eod or stylist.get_current_now() < (
                    stylist_eod - stylist.service_time_gap -
                    datetime.timedelta(minutes=END_OF_DAY_BUFFER_TIME_IN_MINUTES)):
                prices_and_dates_list.append({
                    'date': obj.date,
                    'price': trunc(obj.calculated_price.price),
                    'is_fully_booked': obj.is_fully_booked,
                    'is_working_day': obj.is_working_day,
                    'discount_type': obj.calculated_price.applied_discount.value
                    if obj.calculated_price.applied_discount else None
                })
        return StylistServicePriceSerializer(prices_and_dates_list, many=True).data


class AppointmentValidationMixin(object):

    def validate_datetime_start_at(self, datetime_start_at: datetime.datetime):
        context: Dict = getattr(self, 'context', {})

        stylist: Stylist = context['stylist']
        # check if appointment start is in the past
        if datetime_start_at < timezone.now():
            raise serializers.ValidationError(
                appointment_errors.ERR_APPOINTMENT_IN_THE_PAST
            )

        if not stylist.is_working_day(datetime_start_at):
            raise serializers.ValidationError(
                appointment_errors.ERR_APPOINTMENT_NON_WORKING_DAY
            )

        # check if appointment doesn't fit working hours
        if not stylist.is_working_time(datetime_start_at):
            raise serializers.ValidationError(
                appointment_errors.ERR_APPOINTMENT_OUTSIDE_WORKING_HOURS
            )

        # check if there are intersecting appointments
        if stylist.get_appointments_in_datetime_range(
            datetime_start_at, datetime_start_at + stylist.service_time_gap,
            including_to=True,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST
            ]
        ).exists():
            raise serializers.ValidationError(
                appointment_errors.ERR_APPOINTMENT_INTERSECTION
            )
        return datetime_start_at

    def validate_service_uuid(self, service_uuid: str):
        context: Dict = getattr(self, 'context', {})
        stylist: Stylist = context['stylist']
        if not stylist.services.filter(
            uuid=service_uuid
        ).exists():
            raise serializers.ValidationError(
                appointment_errors.ERR_SERVICE_DOES_NOT_EXIST
            )
        return service_uuid

    def validate_services(self, services):
        if len(services) == 0:
            raise serializers.ValidationError(
                appointment_errors.ERR_SERVICE_REQUIRED
            )
        for service in services:
            self.validate_service_uuid(
                str(service['service_uuid'])
            )
        return services

    def validate_stylist_uuid(self, stylist_uuid: Optional[str]):
        context: Dict = getattr(self, 'context', {})
        user: User = context['user']
        user.client.preferred_stylists.filter(stylist__uuid=stylist_uuid).exists()
        if stylist_uuid:
            if not Stylist.objects.filter(
                    uuid=stylist_uuid,
            ).exists():
                raise serializers.ValidationError(
                    appointment_errors.ERR_STYLIST_DOES_NOT_EXIST
                )
            if not user.client.preferred_stylists.filter(
                    stylist__uuid=stylist_uuid
            ).exists():
                raise serializers.ValidationError(
                    appointment_errors.ERR_NOT_A_PREFERRED_STYLIST
                )

        return stylist_uuid


class AppointmentSerializer(FormattedErrorMessageMixin,
                            AppointmentValidationMixin, serializers.ModelSerializer):

    uuid = serializers.UUIDField(read_only=True)
    stylist_uuid = serializers.UUIDField(required=True, source='stylist.uuid')
    datetime_start_at = serializers.DateTimeField()
    services = AppointmentServiceSerializer(many=True)
    stylist_first_name = serializers.CharField(read_only=True, source='stylist.first_name')
    stylist_last_name = serializers.CharField(read_only=True, source='stylist.last_name')
    stylist_phone = serializers.CharField(read_only=True, source='stylist.phone')
    profile_photo_url = serializers.CharField(
        read_only=True, source='stylist.get_profile_photo_url')
    salon_name = serializers.CharField(
        source='stylist.salon.name', allow_null=True, required=False
    )

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
        max_digits=4, decimal_places=0, coerce_to_string=False, read_only=True,
    )
    tax_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=3, coerce_to_string=False, read_only=True
    )
    card_fee_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=3, coerce_to_string=False, read_only=True
    )
    has_tax_included = serializers.NullBooleanField(read_only=True)
    has_card_fee_included = serializers.NullBooleanField(read_only=True)
    duration_minutes = DurationMinuteField(source='duration', read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'uuid', 'stylist_uuid', 'stylist_first_name', 'stylist_last_name', 'stylist_phone',
            'profile_photo_url', 'salon_name', 'datetime_start_at', 'duration_minutes',
            'status', 'total_tax', 'total_card_fee', 'total_client_price_before_tax',
            'services', 'grand_total', 'has_tax_included', 'has_card_fee_included',
            'tax_percentage', 'card_fee_percentage',
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
            client_of_stylist, created = ClientOfStylist.objects.get_or_create(
                stylist=stylist, client=client, defaults={
                    'first_name': client.user.first_name,
                    'last_name': client.user.last_name,
                    'phone': client.user.phone
                })

            data['client'] = client_of_stylist
            data['stylist'] = stylist
            data['created_by'] = client.user
            data['client_first_name'] = client.user.first_name
            data['client_last_name'] = client.user.last_name
            data['client_phone'] = client.user.phone

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
                include_card_fee=DEFAULT_HAS_CARD_FEE_INCLUDED,
                include_tax=DEFAULT_HAS_TAX_INCLUDED
            )
            for k, v in appointment_prices._asdict().items():
                setattr(appointment, k, v)
            appointment.save()
            appointment.append_status_history(updated_by=stylist.user)

        return appointment


class AppointmentUpdateSerializer(AppointmentSerializer):
    stylist_uuid = serializers.UUIDField(source='stylist.uuid', read_only=True)
    status = serializers.CharField(read_only=False, required=False)

    @staticmethod
    @transaction.atomic
    def _update_appointment_services(
            appointment: Appointment, service_records: List[Dict]
    ) -> None:
        """Replace existing appointment services preserving added on appointment creation"""
        stylist_services = appointment.stylist.services
        services_to_keep: List[uuid.UUID] = [
            service_record['service_uuid'] for service_record in service_records
        ]
        # Delete services which may have been added during appointment creation,
        # but are removed during the checkout. E.g. client had decided to change the
        # service.
        appointment.services.all().exclude(service_uuid__in=services_to_keep).delete()

        # Add new services supplied during the checkout. These are new services, so
        # no discounts will be applied (discount applies only during appointment's
        # initial creation

        for service_record in service_records:
            service_uuid: uuid.UUID = service_record['service_uuid']
            service_client_price: Optional[Decimal] = (
                service_record['client_price'] if 'client_price' in service_record else None)
            try:
                appointment_service: AppointmentService = (
                    appointment.services.get(service_uuid=service_uuid))
                # service already exists, so we will not re-write it
                if service_client_price:
                    appointment_service.set_client_price(service_client_price)
                continue
            except AppointmentService.DoesNotExist:
                service: StylistService = stylist_services.get(uuid=service_uuid)
                AppointmentService.objects.create(
                    appointment=appointment,
                    service_uuid=service.uuid,
                    service_name=service.name,
                    duration=service.duration,
                    regular_price=service.regular_price,
                    calculated_price=service.regular_price,
                    client_price=service_client_price if service_client_price
                    else service.regular_price,
                    is_price_edited=True if service_client_price else False,
                    applied_discount=None,
                    is_original=False
                )

    def save(self, **kwargs):

        status = self.validated_data.get('status', self.instance.status)
        user: User = self.context['user']
        appointment: Appointment = self.instance
        with transaction.atomic():
            if 'services' in self.validated_data:
                self._update_appointment_services(
                    appointment, self.validated_data['services']
                )
            total_client_price_before_tax: Decimal = appointment.services.aggregate(
                total_before_tax=Coalesce(Sum('client_price'), 0)
            )['total_before_tax']

            # update final prices and save appointment

            appointment_prices: AppointmentPrices = calculate_appointment_prices(
                price_before_tax=total_client_price_before_tax,
                include_card_fee=self.instance.has_card_fee_included,
                include_tax=self.instance.has_tax_included
            )

            for k, v in appointment_prices._asdict().items():
                setattr(appointment, k, v)

            if appointment.status != status:
                appointment.status = status
                appointment.append_status_history(updated_by=user)

            appointment.save(**kwargs)

        return appointment

    def validate_status(self, status: AppointmentStatus) -> AppointmentStatus:
        if status not in APPOINTMENT_CLIENT_SETTABLE_STATUSES:
            raise serializers.ValidationError(
                appointment_errors.ERR_STATUS_NOT_ALLOWED
            )
        return status

    def validate(self, attrs):
        status = self.instance.status
        if status != AppointmentStatus.NEW:
            raise serializers.ValidationError(appointment_errors.ERR_CANNOT_MODIFY_APPOINTMENT)
        return attrs


class AvailableDateSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    date = serializers.DateField()
    stylist_uuid = serializers.UUIDField()


class TimeSlotSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    is_booked = serializers.BooleanField()


class HomeSerializer(serializers.Serializer):
    upcoming = AppointmentSerializer(many=True)
    last_visited = AppointmentSerializer()


class HistorySerializer(serializers.Serializer):
    appointments = AppointmentSerializer(many=True)


class AppointmentPreviewRequestSerializer(
    FormattedErrorMessageMixin, AppointmentValidationMixin, serializers.Serializer
):
    stylist_uuid = serializers.UUIDField()
    datetime_start_at = serializers.DateTimeField()
    services = AppointmentServiceSerializer(many=True, required=True, allow_empty=False)

    def to_internal_value(self, data):
        data = super(AppointmentPreviewRequestSerializer, self).to_internal_value(data)
        data['has_tax_included'] = DEFAULT_HAS_TAX_INCLUDED
        data['has_card_fee_included'] = DEFAULT_HAS_CARD_FEE_INCLUDED
        return data


class AppointmentPreviewResponseSerializer(serializers.Serializer):
    stylist_uuid = serializers.UUIDField(source='stylist.uuid', read_only=True)
    stylist_first_name = serializers.CharField(source='stylist.user.first_name', read_only=True)
    stylist_last_name = serializers.CharField(source='stylist.user.last_name', read_only=True)
    stylist_phone = serializers.CharField(source='stylist.user.phone', read_only=True)
    datetime_start_at = serializers.DateTimeField(read_only=True)
    status = serializers.CharField(read_only=True)
    salon_name = serializers.CharField(
        source='stylist.salon.name', required=False, allow_null=True)
    profile_photo_url = serializers.CharField(
        source='stylist.get_profile_photo_url', allow_null=True)

    regular_price = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True,
    )
    client_price = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )
    duration_minutes = DurationMinuteField(source='duration', read_only=True)
    grand_total = serializers.DecimalField(
        max_digits=4, decimal_places=0, coerce_to_string=False, read_only=True,
    )
    total_client_price_before_tax = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )
    total_tax = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )
    total_card_fee = serializers.DecimalField(
        max_digits=6, decimal_places=2, coerce_to_string=False, read_only=True
    )
    tax_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=3, coerce_to_string=False, read_only=True
    )
    card_fee_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=3, coerce_to_string=False, read_only=True
    )
    has_tax_included = serializers.BooleanField(read_only=True)
    has_card_fee_included = serializers.BooleanField(read_only=True)
    services = AppointmentServiceSerializer(many=True)
