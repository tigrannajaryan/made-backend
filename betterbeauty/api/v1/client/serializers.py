import datetime
import decimal
import uuid
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Sum
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
    StylistServicePriceSerializer,
)
from appointment.constants import (
    APPOINTMENT_CLIENT_SETTABLE_STATUSES,
    DEFAULT_HAS_CARD_FEE_INCLUDED, DEFAULT_HAS_TAX_INCLUDED,
    ErrorMessages as appointment_errors
)
from appointment.models import Appointment, AppointmentService
from appointment.types import AppointmentStatus
from client.models import Client, PreferredStylist
from client.types import CLIENT_PRIVACY_CHOICES, ClientPrivacy
from core.models import User
from core.types import AppointmentPrices
from core.utils import calculate_appointment_prices
from integrations.slack import (
    send_slack_auto_booking_notification,
    send_slack_client_profile_update,
)
from notifications.utils import (
    cancel_new_appointment_notification,
    generate_client_cancelled_appointment_notification,
    generate_new_appointment_notification,
)
from pricing import CalculatedPrice
from salon.models import (
    Invitation,
    ServiceCategory,
    Stylist,
    StylistService,
)
from salon.types import InvitationStatus
from salon.utils import (
    calculate_price_and_discount_for_client_on_date,
)


class ClientProfileSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    phone = PhoneNumberField(read_only=True)
    profile_photo_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    profile_photo_url = serializers.CharField(
        source='client.get_profile_photo_url', read_only=True)
    birthday = serializers.DateField(source='client.birthday', required=False, )
    zip_code = serializers.CharField(source='client.zip_code', max_length=10,
                                     required=False, allow_blank=True, allow_null=True)
    email = serializers.CharField(source='client.email',
                                  required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(source='client.city', read_only=True)
    state = serializers.CharField(source='client.state', read_only=True)

    privacy = serializers.ChoiceField(
        source='client.privacy', choices=CLIENT_PRIVACY_CHOICES, required=False
    )
    profile_completeness = serializers.DecimalField(source='client.profile_completeness',
                                                    max_digits=3, decimal_places=2,
                                                    read_only=True, coerce_to_string=False,
                                                    rounding=decimal.ROUND_HALF_UP)

    google_calendar_integrated = serializers.SerializerMethodField()
    has_seen_educational_screens = serializers.BooleanField(
        source='client.has_seen_educational_screens', required=False)
    google_api_key = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'phone', 'profile_photo_id', 'profile_photo_url',
            'zip_code', 'birthday', 'email', 'city', 'state', 'privacy',
            'has_seen_educational_screens', 'google_api_key',
            'google_calendar_integrated', 'profile_completeness',
        ]

    def get_google_api_key(self, user: User):
        return settings.GOOGLE_AUTOCOMPLETE_API_KEY

    def get_google_calendar_integrated(self, instance: User) -> bool:
        return bool(
            instance.client.google_access_token and
            instance.client.google_refresh_token
        )

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
        is_profile_already_complete = False
        if self.instance.first_name and self.instance.photo:
            is_profile_already_complete = True
        should_save_photo = False
        profile_photo_id = None
        if 'profile_photo_id' in self.validated_data:
            should_save_photo = True
            profile_photo_id = self.validated_data.pop('profile_photo_id')
        client_data = self.validated_data.pop('client', None)
        user: User = self.instance
        client = user.client
        if should_save_photo:
            save_profile_photo(
                user, profile_photo_id
            )
        if client_data:
            fields_to_save: List[str] = list(client_data.keys())
            if client.zip_code != client_data.get('zip_code', client.zip_code):
                client.city = None
                client.state = None
                client.location = None
                client.is_address_geocoded = False
                client.last_geo_coded = None
                fields_to_save.extend([
                    'city', 'state', 'location', 'is_address_geocoded', 'last_geo_coded'])
            for k, v in client_data.items():
                setattr(client, k, v)
        client.save()
        user = super(ClientProfileSerializer, self).save(**kwargs)
        if not is_profile_already_complete:
            send_slack_client_profile_update(client)
        return user


class ClientProfileStatusSerializer(serializers.ModelSerializer):
    has_name = serializers.SerializerMethodField()
    has_zipcode = serializers.SerializerMethodField()
    has_email = serializers.SerializerMethodField()
    has_picture_set = serializers.SerializerMethodField()
    has_preferred_stylist_set = serializers.SerializerMethodField()
    has_booked_appointment = serializers.SerializerMethodField()
    has_past_visit = serializers.SerializerMethodField()
    has_invitation = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            'has_name', 'has_zipcode', 'has_email', 'has_picture_set', 'has_invitation',
            'has_preferred_stylist_set', 'has_booked_appointment', 'has_past_visit',
            'has_seen_educational_screens',
        ]

    def get_has_name(self, client: Client) -> bool:
        full_name = client.user.get_full_name()
        has_name = full_name and len(full_name) > 1
        return bool(has_name)

    def get_has_zipcode(self, client: Client) -> bool:
        return bool(client.zip_code)

    def get_has_email(self, client: Client) -> bool:
        return bool(client.email)

    def get_has_picture_set(self, client: Client) -> bool:
        return bool(client.user.photo)

    def get_has_preferred_stylist_set(self, client: Client) -> bool:
        has_pref_stylist = PreferredStylist.objects.filter(
            client=client, deleted_at__isnull=True).exists()
        return has_pref_stylist

    def get_has_booked_appointment(self, client: Client) -> bool:
        has_appointments = client.get_appointments_in_datetime_range(exclude_statuses=[
            AppointmentStatus.CANCELLED_BY_STYLIST,
            AppointmentStatus.CANCELLED_BY_CLIENT,
        ]).exists()
        return has_appointments

    def get_has_past_visit(self, client: Client) -> bool:
        return client.get_past_appointments().exists()

    def get_has_invitation(self, client: Client) -> bool:
        has_invitation: bool = Invitation.objects.filter(
            phone=client.user.phone, status=InvitationStatus.INVITED).exists()
        return has_invitation


class PreferredStylistSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):

    preference_uuid = serializers.UUIDField(source='uuid')
    uuid = serializers.UUIDField(source='stylist.uuid')
    salon_name = serializers.CharField(
        source='stylist.salon.name', allow_null=True, required=False
    )
    instagram_url = serializers.CharField(
        source="stylist.instagram_url", read_only=True
    )
    website_url = serializers.CharField(
        source="stylist.website_url", read_only=True
    )
    salon_address = serializers.CharField(source='stylist.salon.address', allow_null=True)
    profile_photo_url = serializers.CharField(
        read_only=True, source='stylist.get_profile_photo_url'
    )
    first_name = serializers.CharField(source='stylist.user.first_name')
    last_name = serializers.CharField(source='stylist.user.last_name')
    phone = serializers.CharField(source='stylist.public_phone_or_user_phone', read_only=True)
    followers_count = serializers.SerializerMethodField()
    is_profile_bookable = serializers.BooleanField(
        source='stylist.is_profile_bookable', read_only=True
    )
    specialities = serializers.ListField(source='stylist.get_specialities_list', read_only=True)
    instagram_integrated = serializers.BooleanField(
        source='stylist.instagram_integrated', read_only=True
    )

    class Meta:
        model = PreferredStylist
        fields = ['uuid', 'salon_name', 'salon_address', 'profile_photo_url',
                  'first_name', 'last_name', 'phone', 'preference_uuid', 'instagram_url',
                  'website_url', 'followers_count', 'is_profile_bookable', 'specialities',
                  'instagram_integrated',
                  ]

    def get_followers_count(self, preferred_stylist: PreferredStylist):
        return preferred_stylist.stylist.get_preferred_clients().filter(
            privacy=ClientPrivacy.PUBLIC
        ).count()


class ClientPreferredStylistSerializer(serializers.ModelSerializer):

    stylists = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ['stylists', ]

    def get_stylists(self, client: Client):
        preferred_stylists = client.preferred_stylists.filter(stylist__deactivated_at=None)
        return PreferredStylistSerializer(preferred_stylists, many=True).data


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
            Invitation.objects.filter(phone=client.user.phone, stylist=stylist,
                                      status=InvitationStatus.INVITED).update(
                status=InvitationStatus.ACCEPTED, accepted_at=timezone.now(),
                created_client=client)
            self.instance = preferred_stylist
            return self.instance


class StylistServiceListSerializer(FormattedErrorMessageMixin, serializers.ModelSerializer):
    stylist_uuid = serializers.UUIDField(read_only=True, source='uuid')
    categories = serializers.SerializerMethodField(read_only=True)

    class Meta:
        fields = ['stylist_uuid', 'categories']
        model = Stylist

    def get_categories(self, stylist: Stylist):
        category_queryset = ServiceCategory.objects.all().order_by(
            '-weight', 'name', 'uuid'
        ).distinct('weight', 'name', 'uuid')
        return StylistServiceCategoryDetailsSerializer(
            category_queryset,
            context={'stylist': stylist},
            many=True
        ).data


class ServicePricingRequestSerializer(FormattedErrorMessageMixin, serializers.Serializer):
    service_uuids = serializers.ListField(child=serializers.UUIDField())
    stylist_uuid = serializers.UUIDField(required=False, allow_null=True)

    def validate_service_uuids(self, service_uuids: List[str]):
        if not StylistService.objects.filter(uuid__in=service_uuids, stylist__deactivated_at=None
                                             ).count() == len(service_uuids):
            raise serializers.ValidationError(
                appointment_errors.ERR_SERVICE_DOES_NOT_EXIST
            )
        return service_uuids

    def validate_stylist_uuid(self, stylist_uuid: str):
        is_valid_stylist = Stylist.objects.filter(uuid=stylist_uuid, deactivated_at=None).exists()
        if is_valid_stylist:
            return stylist_uuid
        raise serializers.ValidationError(ErrorMessages.ERR_INVALID_STYLIST_UUID)

    def validate(self, attrs):
        if ('service_uuids' in attrs and len(attrs['service_uuids'])) or (
                'stylist_uuid' in attrs and attrs['stylist_uuid']):
            return attrs
        raise serializers.ValidationError(ErrorMessages.ERR_NO_STYLIST_OR_SERVICE_UUIDS)


class PricingHintSerializer(serializers.Serializer):
    priority = serializers.IntegerField(read_only=True)
    hint = serializers.CharField(read_only=True)


class ServicePricingSerializer(serializers.Serializer):
    service_uuids = serializers.ListField(child=serializers.UUIDField())
    stylist_uuid = serializers.UUIDField(read_only=True)
    prices = StylistServicePriceSerializer(many=True, read_only=True)
    pricing_hints = PricingHintSerializer(many=True, read_only=True)

    class Meta:
        fields = ['service_uuid', 'service_name', 'prices', 'pricing_hints', ]


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
        partially_intersecting_appointments = stylist.get_appointments_in_datetime_range(
            datetime_start_at - (stylist.service_time_gap / 2),
            datetime_start_at + (stylist.service_time_gap / 2),
            including_to=True,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST
            ]
        )
        for appointment in partially_intersecting_appointments:
            if (datetime_start_at - (stylist.service_time_gap / 2) < (
                    appointment.datetime_start_at) <= (
                    datetime_start_at + (stylist.service_time_gap / 2))):
                raise serializers.ValidationError(
                    appointment_errors.ERR_APPOINTMENT_INTERSECTION
                )
        return datetime_start_at

    def validate_service_uuid(self, service_uuid: str):
        context: Dict = getattr(self, 'context', {})
        stylist: Stylist = context['stylist']
        if stylist and not stylist.services.filter(
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
            if 'service_uuid' in service:
                self.validate_service_uuid(
                    str(service['service_uuid'])
                )
            else:
                raise serializers.ValidationError(
                    appointment_errors.ERR_SERVICE_REQUIRED
                )
        return services

    def validate_stylist_uuid(self, stylist_uuid: Optional[str]):
        context: Dict = getattr(self, 'context', {})
        user: User = context['user']
        if stylist_uuid:
            if not Stylist.objects.filter(
                    uuid=stylist_uuid,
                    deactivated_at=None
            ).exists():
                raise serializers.ValidationError(
                    appointment_errors.ERR_STYLIST_DOES_NOT_EXIST
                )
            if not user.client.preferred_stylists.filter(
                    stylist__uuid=stylist_uuid,
                    stylist__deactivated_at=None
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
    stylist_phone = serializers.CharField(read_only=True,
                                          source='stylist.public_phone_or_user_phone')
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
            preferred_stylist, created = PreferredStylist.objects.get_or_create(
                stylist=stylist, client=client
            )

            data['client'] = client
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
                    service=service, client=client, date=datetime_start_at.date()
                )
                services_with_client_prices.append((service, client_price))
            appointment: Appointment = super(AppointmentSerializer, self).create(data)
            total_client_price_before_tax: Decimal = Decimal(0)
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
        generate_new_appointment_notification(appointment)
        send_slack_auto_booking_notification(appointment)
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
                # If there's at least one service in the appointment which originally has
                # a discount - we will copy discount information from that service instead
                # of calculating it based on today's information
                original_service: Optional[AppointmentService] = appointment.services.filter(
                    is_original=True, applied_discount__isnull=False
                ).first()
                calc_price: CalculatedPrice = calculate_price_and_discount_for_client_on_date(
                    service=service,
                    client=appointment.client, date=appointment.datetime_start_at.date(),
                    based_on_existing_service=original_service
                )
                AppointmentService.objects.create(
                    appointment=appointment,
                    service_uuid=service.uuid,
                    service_name=service.name,
                    duration=service.duration,
                    regular_price=service.regular_price,
                    calculated_price=calc_price.price,
                    client_price=service_client_price if service_client_price
                    else calc_price.price,
                    is_price_edited=True if service_client_price else False,
                    applied_discount=calc_price.applied_discount,
                    discount_percentage=calc_price.discount_percentage,
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
                if status == AppointmentStatus.CANCELLED_BY_CLIENT:
                    generate_client_cancelled_appointment_notification(appointment)
                appointment.status = status
                appointment.append_status_history(updated_by=user)

            appointment.save(**kwargs)
            # If status is changing try to cancel new appointment notification if it's not
            # sent yet
            if (
                status != AppointmentStatus.NEW and
                appointment.stylist_new_appointment_notification
            ):
                cancel_new_appointment_notification(appointment)
                appointment.refresh_from_db()

        return appointment

    def validate_status(self, status: AppointmentStatus) -> AppointmentStatus:
        if status == AppointmentStatus.CHECKED_OUT:
            # we only allow clients to move appointments to checked out state
            # on the actual date of appointment
            stylist: Stylist = self.instance.stylist
            appointment_date: datetime.date = stylist.with_salon_tz(
                self.instance.datetime_start_at
            ).date()
            today = stylist.with_salon_tz(timezone.now()).date()
            if appointment_date != today:
                raise serializers.ValidationError(
                    appointment_errors.ERR_STATUS_NOT_ALLOWED
                )
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


class StylistPhotoUrlSerializer(serializers.Serializer):
    photo_url = serializers.URLField(source='stylist.get_profile_photo_url')


class HomeSerializer(serializers.Serializer):
    upcoming = AppointmentSerializer(many=True)
    last_visited = AppointmentSerializer()
    preferred_stylists = StylistPhotoUrlSerializer(many=True)


class HistorySerializer(serializers.Serializer):
    appointments = AppointmentSerializer(many=True)


class AppointmentPreviewRequestSerializer(
    FormattedErrorMessageMixin, AppointmentValidationMixin, serializers.Serializer
):
    stylist_uuid = serializers.UUIDField(required=True, allow_null=False)
    appointment_uuid = serializers.UUIDField(required=False, default=None)
    datetime_start_at = serializers.DateTimeField(required=False, default=None)
    services = AppointmentServiceSerializer(many=True, required=True, allow_empty=False)

    def to_internal_value(self, data):
        data = super(AppointmentPreviewRequestSerializer, self).to_internal_value(data)
        data['has_tax_included'] = DEFAULT_HAS_TAX_INCLUDED
        data['has_card_fee_included'] = DEFAULT_HAS_CARD_FEE_INCLUDED
        return data

    def validate_datetime_start_at(self, datetime_start_at: datetime.datetime):
        # if the appointment_uuid was passed on - we don't need to check for correctness
        # of it; appointment already exists
        if 'appointment_uuid' in self.initial_data:
            return datetime_start_at
        # otherwise, pass validation to the mixin
        return super(AppointmentPreviewRequestSerializer, self).validate_datetime_start_at(
            datetime_start_at
        )

    def validate_appointment_uuid(self, appointment_uuid: Optional[str]):
        client: Client = self.context['client']
        if appointment_uuid is not None:
            if not client.appointments.filter(uuid=appointment_uuid).exists():
                raise ValidationError(appointment_errors.ERR_APPOINTMENT_DOESNT_EXIST)
        return appointment_uuid


class AppointmentPreviewResponseSerializer(serializers.Serializer):
    stylist_uuid = serializers.UUIDField(source='stylist.uuid', read_only=True)
    stylist_first_name = serializers.CharField(source='stylist.user.first_name', read_only=True)
    stylist_last_name = serializers.CharField(source='stylist.user.last_name', read_only=True)
    stylist_phone = serializers.CharField(source='stylist.public_phone_or_user_phone',
                                          read_only=True)
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


class FollowerSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='user.first_name')
    last_name = serializers.CharField(source='user.last_name')
    booking_count = serializers.SerializerMethodField()
    photo_url = serializers.CharField(source='get_profile_photo_url', allow_null=True)

    class Meta:
        model = Client
        fields = ['uuid', 'first_name', 'last_name', 'booking_count', 'photo_url', ]

    def get_booking_count(self, client: Client):
        stylist: Stylist = self.context['stylist']
        return Appointment.objects.filter(
            stylist=stylist,
            client=client,
        ).exclude(
            status__in=[
                AppointmentStatus.NO_SHOW,
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST
            ]
        ).count()


class SearchStylistSerializer(
    FormattedErrorMessageMixin,
    serializers.ModelSerializer
):
    uuid = serializers.UUIDField(read_only=True)

    salon_name = serializers.CharField(
        source='salon__name', allow_null=True, required=False
    )
    salon_address = serializers.CharField(source='salon__address', allow_null=True)

    salon_city = serializers.CharField(source='salon__city', required=False)
    salon_zipcode = serializers.CharField(source='salon__zip_code', required=False)
    salon_state = serializers.CharField(source='salon__state', required=False)

    profile_photo_url = serializers.SerializerMethodField()

    first_name = serializers.CharField(source='user__first_name')
    last_name = serializers.CharField(source='user__last_name')
    phone = serializers.SerializerMethodField()
    is_profile_bookable = serializers.SerializerMethodField()
    followers_count = serializers.IntegerField()
    specialities = serializers.SerializerMethodField()
    preference_uuid = serializers.CharField()
    instagram_integrated = serializers.BooleanField(read_only=True)

    class Meta:
        model = Stylist
        fields = [
            'uuid', 'first_name', 'last_name', 'phone', 'profile_photo_url',
            'salon_name', 'salon_address', 'instagram_url',
            'website_url', 'salon_city', 'salon_zipcode', 'salon_state', 'is_profile_bookable',
            'followers_count', 'specialities', 'preference_uuid', 'instagram_integrated',
        ]

    def get_phone(self, stylist: Stylist):
        return stylist.salon__public_phone or stylist.user__phone

    def get_specialities(self, stylist: Stylist):
        if stylist.sp_text:
            return [x.strip() for x in stylist.sp_text.split(',')]
        return []

    def get_is_profile_bookable(self, stylist: Stylist):
        return bool(
            stylist.user__phone and
            stylist.services_count and
            stylist.has_business_hours_set
        )

    def get_profile_photo_url(self, stylist: Stylist):
        return default_storage.url(stylist.user__photo) if stylist.user__photo else None


class AppointmentServiceListUpdateSerializer(
    FormattedErrorMessageMixin, serializers.ModelSerializer
):
    services = AppointmentServiceSerializer(many=True)
