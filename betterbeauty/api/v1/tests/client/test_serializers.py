import datetime
from decimal import Decimal

import mock
import pytest
import pytz

from django.conf import settings
from django.utils import timezone
from django_dynamic_fixture import G
from freezegun import freeze_time

from api.v1.client.serializers import (
    AppointmentPreviewRequestSerializer,
    AppointmentPreviewResponseSerializer,
    AppointmentSerializer,
    AppointmentUpdateSerializer,
    AppointmentValidationMixin,
    ClientProfileSerializer,
    ServicePricingRequestSerializer,
)
from appointment.constants import ErrorMessages as appointment_errors
from appointment.models import Appointment, AppointmentService
from appointment.preview import (
    AppointmentPreviewRequest,
    AppointmentPreviewResponse,
    AppointmentServicePreview,
)
from appointment.types import AppointmentStatus
from client.models import Client, ClientPrivacy, PreferredStylist
from core.models import User
from core.types import UserRole, Weekday
from core.utils import calculate_card_fee, calculate_tax
from pricing import CalculatedPrice
from salon.models import (
    Salon,
    Stylist,
    StylistService,
)


class TestAppointmentSerializer(object):
    @freeze_time('2018-05-17 15:30:00 UTC')
    @pytest.mark.django_db
    def test_validate_start_time(self, stylist_data: Stylist, client_data: Client):
        stylist_data.service_time_gap = datetime.timedelta(minutes=30)
        stylist_data.save(update_fields=['service_time_gap'])
        service: StylistService = G(
            StylistService,
            stylist=stylist_data, duration=datetime.timedelta(minutes=30),
            regular_price=50
        )
        G(PreferredStylist, stylist=stylist_data, client=client_data)
        stylist_data.available_days.filter(weekday=Weekday.THURSDAY).update(
            is_available=True,
            work_start_at=datetime.time(8, 0),
            work_end_at=datetime.time(17, 0)
        )
        past_datetime: datetime.datetime = datetime.datetime(
            2018, 5, 17, 14, 00, tzinfo=pytz.utc)
        data = {
            'stylist_uuid': stylist_data.uuid,
            'services': [
                {
                    'service_uuid': service.uuid,
                }
            ],
            'datetime_start_at': past_datetime.isoformat()
        }
        serializer = AppointmentSerializer(data=data, context={
            'stylist': stylist_data, 'user': client_data.user})
        serializer.is_valid()
        assert(serializer.is_valid(raise_exception=False) is False)
        assert(
            {'code': appointment_errors.ERR_APPOINTMENT_IN_THE_PAST} in
            serializer.errors['field_errors'].get('datetime_start_at')
        )

        outside_working_hours: datetime.datetime = datetime.datetime(
            2018, 5, 17, 19, 00, tzinfo=pytz.utc)
        data = {
            'stylist_uuid': stylist_data.uuid,
            'services': [
                {
                    'service_uuid': service.uuid,
                }
            ],
            'datetime_start_at': outside_working_hours.isoformat()
        }
        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert (serializer.is_valid(raise_exception=False) is False)
        assert (
            {'code': appointment_errors.ERR_APPOINTMENT_OUTSIDE_WORKING_HOURS} in
            serializer.errors['field_errors'].get('datetime_start_at')
        )

        available_time: datetime.datetime = stylist_data.with_salon_tz(datetime.datetime(
            2018, 5, 17, 16, 00, tzinfo=pytz.utc))

        data = {
            'stylist_uuid': stylist_data.uuid,
            'services': [
                {
                    'service_uuid': service.uuid,
                }
            ],
            'datetime_start_at': available_time.isoformat()
        }
        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert (serializer.is_valid(raise_exception=False) is True)

        # add another appointment to check intersection
        previous_appointment = G(
            Appointment, stylist=stylist_data,
            datetime_start_at=datetime.datetime(2018, 5, 17, 15, 50, tzinfo=pytz.utc),
            status=AppointmentStatus.NEW
        )

        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert (serializer.is_valid(raise_exception=False) is False)
        assert (
            {'code': appointment_errors.ERR_APPOINTMENT_INTERSECTION} in
            serializer.errors['field_errors'].get('datetime_start_at')
        )
        previous_appointment.delete()
        # check next appointment
        next_appointment = G(
            Appointment, stylist=stylist_data,
            datetime_start_at=datetime.datetime(2018, 5, 17, 16, 20, tzinfo=pytz.utc),
            status=AppointmentStatus.NEW,
        )
        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert (serializer.is_valid(raise_exception=False) is True)
        next_appointment.delete()
        # try inner appointment
        G(
            Appointment, stylist=stylist_data,
            datetime_start_at=datetime.datetime(2018, 5, 17, 16, 10, tzinfo=pytz.utc),
            status=AppointmentStatus.NEW
        )
        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert (serializer.is_valid(raise_exception=False) is False)
        assert (
            {'code': appointment_errors.ERR_APPOINTMENT_INTERSECTION} in
            serializer.errors['field_errors'].get('datetime_start_at')
        )

    @freeze_time('2018-05-17 15:30:00 UTC')
    @pytest.mark.django_db
    def test_create_without_client(self, stylist_data: Stylist, client_data: Client, mocker):
        service: StylistService = G(
            StylistService,
            stylist=stylist_data, duration=datetime.timedelta(minutes=30),
            regular_price=50
        )
        stylist_data.available_days.filter(weekday=Weekday.THURSDAY).update(
            is_available=True,
            work_start_at=datetime.time(8, 0),
            work_end_at=datetime.time(17, 0)
        )
        available_time: datetime.datetime = datetime.datetime(
            2018, 5, 17, 16, 00, tzinfo=pytz.utc)

        data = {
            'stylist_uuid': stylist_data.uuid,
            'services': [
                {
                    'service_uuid': service.uuid,
                },
            ],
            'datetime_start_at': available_time.isoformat()
        }
        G(
            PreferredStylist, client=client_data, stylist=stylist_data
        )
        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert(serializer.is_valid() is True)
        appointment: Appointment = serializer.save()

        assert(appointment.total_client_price_before_tax == 40)
        assert(appointment.duration == service.duration)
        assert(appointment.client_first_name == client_data.user.first_name)
        assert (appointment.client is not None)
        client: Client = appointment.client
        assert(client.user.first_name == client_data.user.first_name)
        assert(client.user.phone == client_data.user.phone)
        assert(appointment.services.count() == 1)
        original_service: AppointmentService = appointment.services.first()
        assert(original_service.is_original is True)
        assert(original_service.regular_price == service.regular_price)
        assert(original_service.client_price == 40)
        assert(original_service.service_uuid == service.uuid)
        assert(original_service.service_name == service.name)

    @freeze_time('2018-05-17 15:30:00 UTC')
    @pytest.mark.django_db
    def test_create_with_client(self, stylist_data: Stylist, client_data: Client, mocker):
        slack_mock = mocker.patch(
            'api.v1.client.serializers.send_slack_auto_booking_notification'
        )
        service: StylistService = G(
            StylistService,
            stylist=stylist_data, duration=datetime.timedelta(minutes=30),
            regular_price=50
        )
        stylist_data.available_days.filter(weekday=Weekday.THURSDAY).update(
            is_available=True,
            work_start_at=datetime.time(8, 0),
            work_end_at=datetime.time(17, 0)
        )
        available_time: datetime.datetime = datetime.datetime(
            2018, 5, 17, 16, 00, tzinfo=pytz.utc)

        data = {
            'stylist_uuid': stylist_data.uuid,
            'services': [
                {
                    'service_uuid': service.uuid,
                },
            ],
            'datetime_start_at': available_time.isoformat()
        }
        # check client which is not related to stylist, i.e. no prior appointments
        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert(serializer.is_valid() is False)
        assert('stylist_uuid' in serializer.errors['field_errors'])

        G(
            Appointment,
            client=client_data, stylist=stylist_data, created_by=stylist_data.user,
            datetime_start_at=stylist_data.with_salon_tz(datetime.datetime(2018, 5, 15, 15, 30))
        )
        G(
            PreferredStylist, client=client_data, stylist=stylist_data
        )
        serializer = AppointmentSerializer(
            data=data, context={'stylist': stylist_data, 'user': client_data.user})
        assert (serializer.is_valid() is True)
        appointment: Appointment = serializer.save()

        assert (
            appointment.total_client_price_before_tax == 40
        )
        assert(appointment.duration == service.duration)
        assert(appointment.client_first_name == client_data.user.first_name)
        assert(appointment.client == client_data)

        assert (appointment.services.count() == 1)
        original_service: AppointmentService = appointment.services.first()
        assert (original_service.is_original is True)
        assert (original_service.regular_price == service.regular_price)
        assert (original_service.client_price == 40)
        assert (original_service.service_uuid == service.uuid)
        assert (original_service.service_name == service.name)
        assert(slack_mock.called_once_with(appointment))

    @freeze_time('2018-05-17 10:30:00 UTC')
    @pytest.mark.django_db
    def test_create_pricing(self, stylist_data: Stylist, client_data: Client):
        from salon.models import StylistAvailableWeekDay
        from salon.utils import calculate_price_and_discount_for_client_on_date
        service: StylistService = G(
            StylistService,
            stylist=stylist_data,
            regular_price=200,
            duration=datetime.timedelta()
        )
        appointment_dates = [
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 8, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 9, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 10, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 11, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 12, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 13, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 14, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 15, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 16, 00)
            ),
            stylist_data.with_salon_tz(
                datetime.datetime(2018, 5, 17, 17, 00)
            ),


        ]

        # associate client with stylist
        G(PreferredStylist, client=client_data, stylist=stylist_data)
        G(Appointment, stylist=stylist_data, client=client_data,
          datetime_start_at=stylist_data.with_salon_tz(
              datetime.datetime(2018, 5, 10, 10, 00)
          ))
        stylist_data.available_days.filter(weekday=Weekday.THURSDAY).delete()
        G(StylistAvailableWeekDay, weekday=Weekday.THURSDAY,
          work_start_at=datetime.time(8, 0), work_end_at=datetime.time(22, 00),
          is_available=True, stylist=stylist_data
          )
        for appointment_date in appointment_dates:
            appointment_data = {
                'stylist_uuid': stylist_data.uuid,
                'services': [
                    {
                        'service_uuid': service.uuid,
                    },
                ],
                'datetime_start_at': (
                    appointment_date
                ).isoformat()
            }

            calculated_price: CalculatedPrice = calculate_price_and_discount_for_client_on_date(
                service=service, client=client_data, date=appointment_date.date()
            )
            appointment_serializer = AppointmentSerializer(
                data=appointment_data, context={'stylist': stylist_data, 'user': client_data.user}
            )
            assert(appointment_serializer.is_valid(raise_exception=False) is True)
            appointment: Appointment = appointment_serializer.save()
            appointment_service: AppointmentService = appointment.services.first()
            assert(round(calculated_price.price, 2) == float(appointment_service.client_price))


class TestAppointmentUpdateSerializer(object):

    @pytest.mark.django_db
    def test_validate_status(self, stylist_data: Stylist, client_data: Client):
        appointment = G(
            Appointment,
            duration=datetime.timedelta(minutes=30)
        )
        data = {
            'status': AppointmentStatus.CANCELLED_BY_STYLIST.value
        }
        serializer = AppointmentUpdateSerializer(instance=appointment, data=data, partial=True)
        assert(serializer.is_valid() is False)
        assert(
            {'code': appointment_errors.ERR_STATUS_NOT_ALLOWED} in
            serializer.errors['field_errors']['status']
        )
        data = {
            'status': AppointmentStatus.CHECKED_OUT.value
        }
        serializer = AppointmentUpdateSerializer(instance=appointment, data=data, partial=True)
        assert (serializer.is_valid() is False)
        assert (
            {'code': appointment_errors.ERR_STATUS_NOT_ALLOWED} in
            serializer.errors['field_errors']['status']
        )
        data = {
            'status': AppointmentStatus.CANCELLED_BY_CLIENT.value
        }
        serializer = AppointmentUpdateSerializer(instance=appointment, data=data, partial=True)
        assert(serializer.is_valid() is True)

    @pytest.mark.django_db
    def test_validate_services(self, stylist_data: Stylist, client_data: Client):
        appointment = G(
            Appointment,
            duration=datetime.timedelta(minutes=30)
        )
        stylist_service = G(
            StylistService,

            stylist=appointment.stylist,
            duration=datetime.timedelta(minutes=30)
        )
        appointment_service_valid = G(
            AppointmentService,
            duration=stylist_service.duration,
            service_uuid=stylist_service.uuid,
        )
        appointment_service_invalid = G(
            AppointmentService,
            duration=stylist_service.duration,
        )
        context = {
            'stylist': stylist_service.stylist,
            'user': client_data.user
        }

        data = {
            'status': AppointmentStatus.CANCELLED_BY_CLIENT.value
        }
        G(PreferredStylist, client=client_data, stylist=stylist_data)
        serializer = AppointmentUpdateSerializer(
            instance=appointment, data=data, context=context, partial=True)
        assert (serializer.is_valid() is True)

        data = {
            'services': [
                {'service_uuid': appointment_service_valid.service_uuid}
            ]
        }
        serializer = AppointmentUpdateSerializer(
            instance=appointment, data=data, context=context, partial=True)
        assert (serializer.is_valid() is True)

        data = {
            'services': [
                {'service_uuid': appointment_service_invalid.service_uuid}
            ]
        }
        serializer = AppointmentUpdateSerializer(
            instance=appointment, data=data, context=context, partial=True)
        assert (serializer.is_valid() is False)
        assert (
            {'code': appointment_errors.ERR_SERVICE_DOES_NOT_EXIST} in
            serializer.errors['field_errors']['services']
        )
        appointment.status = AppointmentStatus.CHECKED_OUT
        appointment.save()

    @pytest.mark.django_db
    def test_save_non_checked_out_status(self, stylist_data: Stylist, client_data: Client):
        salon = G(Salon, timezone=pytz.utc)
        stylist = G(Stylist, salon=salon)
        appointment = G(
            Appointment,
            stylist=stylist,
            duration=datetime.timedelta(minutes=30)
        )
        context = {
            'stylist': appointment.stylist,
            'user': client_data.user
        }
        assert(appointment.status == AppointmentStatus.NEW)
        data = {
            'status': AppointmentStatus.CANCELLED_BY_CLIENT.value
        }
        G(PreferredStylist, client=client_data, stylist=stylist)
        serializer = AppointmentUpdateSerializer(
            instance=appointment, data=data, context=context, partial=True)
        assert(serializer.is_valid())
        appointment = serializer.save()
        assert(appointment.status == AppointmentStatus.CANCELLED_BY_CLIENT)

    @pytest.mark.django_db
    def test_save_checked_out_status(self, mocker, stylist_data: Stylist, client_data: Client):
        salon = G(Salon, timezone=pytz.utc)
        stylist = G(Stylist, salon=salon)
        appointment = G(
            Appointment,
            stylist=stylist,
            duration=datetime.timedelta(minutes=30)
        )
        context = {
            'stylist': appointment.stylist,
            'user': client_data.user
        }
        original_service: StylistService = G(
            StylistService, stylist=appointment.stylist,
            duration=datetime.timedelta(30),
            regular_price=20
        )
        G(
            AppointmentService, appointment=appointment,
            service_uuid=original_service.uuid, service_name=original_service.name,
            duration=original_service.duration, is_original=True,
            regular_price=20, client_price=18
        )

        new_service: StylistService = G(
            StylistService, stylist=appointment.stylist,
            duration=datetime.timedelta(30),
            regular_price=40
        )

        assert(appointment.services.count() == 1)

        data = {
            'services': [
                {
                    'service_uuid': original_service.uuid
                },
                {
                    'service_uuid': new_service.uuid
                }
            ]
        }
        G(PreferredStylist, client=client_data, stylist=stylist)
        serializer = AppointmentUpdateSerializer(
            instance=appointment, data=data, context=context, partial=True
        )

        assert(serializer.is_valid() is True)
        saved_appointment: Appointment = serializer.save()
        assert(saved_appointment.services.count() == 2)
        original_appointment_service: AppointmentService = saved_appointment.services.get(
            is_original=True
        )
        assert(original_appointment_service.service_uuid == original_service.uuid)
        assert(original_appointment_service.client_price == 18)
        assert(original_appointment_service.regular_price == 20)

        added_appointment_service: AppointmentService = saved_appointment.services.get(
            is_original=False
        )
        assert(added_appointment_service.service_uuid == new_service.uuid)
        assert(added_appointment_service.client_price == 40)
        assert(added_appointment_service.regular_price == 40)

        total_services_cost = sum([s.client_price for s in saved_appointment.services.all()], 0)
        assert(saved_appointment.total_client_price_before_tax == total_services_cost)
        assert(saved_appointment.grand_total == total_services_cost)
        assert(saved_appointment.total_tax == calculate_tax(Decimal(total_services_cost)))
        assert(
            saved_appointment.total_card_fee == calculate_card_fee(Decimal(total_services_cost))
        )


class TestAppointmentPreviewRequestSerializer(object):
    @pytest.mark.django_db
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_datetime_start_at', lambda s, a: a)
    def test_preview_request(self):
        stylist: Stylist = G(Stylist, service_time_gap=datetime.timedelta(minutes=60))
        service: StylistService = G(
            StylistService, duration=datetime.timedelta(0), stylist=stylist)
        client = G(Client)

        data = {
            'stylist_uuid': stylist.uuid,
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            'services': [
                {'service_uuid': service.uuid},
            ]
        }
        serializer = AppointmentPreviewRequestSerializer(
            data=data, context={
                'user': client.user,
                'stylist': stylist
            }
        )
        assert(not serializer.is_valid(raise_exception=False))

        G(PreferredStylist, client=client, stylist=stylist)
        serializer = AppointmentPreviewRequestSerializer(
            data=data, context={
                'user': client.user,
                'stylist': stylist
            }
        )
        assert (serializer.is_valid(raise_exception=False))

        serializer.validated_data.pop('stylist_uuid')
        preview_request = AppointmentPreviewRequest(**serializer.validated_data)

        assert(preview_request == AppointmentPreviewRequest(
            datetime_start_at=datetime.datetime(
                2018, 1, 1, 0, 0, tzinfo=pytz.UTC
            ).astimezone(pytz.timezone(settings.TIME_ZONE)),
            has_tax_included=True,
            has_card_fee_included=False,
            appointment_uuid=None,
            services=[
                {'service_uuid': service.uuid}
            ]
        ))

        foreign_service = G(
            StylistService, duration=datetime.timedelta(0)
        )
        data = {
            'stylist_uuid': stylist.uuid,
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0),
            'services': [
                {'service_uuid': service.uuid},
                {'service_uuid': foreign_service.uuid}
            ]
        }
        serializer = AppointmentPreviewRequestSerializer(
            data=data, context={
                'user': client.user,
                'stylist': stylist
            }
        )
        assert (not serializer.is_valid(raise_exception=False))


class TestAppointmentPreviewResponseSerializer(object):

    @pytest.mark.django_db
    def test_preview_response(self):
        salon = G(Salon, name='some salon', timezone=pytz.UTC)
        stylist: Stylist = G(
            Stylist, service_time_gap=datetime.timedelta(minutes=60), salon=salon)
        service: StylistService = G(
            StylistService, duration=datetime.timedelta(0), stylist=stylist)

        data = AppointmentPreviewResponse(
            stylist=stylist,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            grand_total=15,
            total_client_price_before_tax=10,
            total_tax=4,
            total_card_fee=1,
            duration=stylist.service_time_gap,
            conflicts_with=Appointment.objects.none(),
            has_tax_included=True,
            has_card_fee_included=False,
            services=[
                AppointmentServicePreview(
                    service_name=service.name,
                    service_uuid=service.uuid,
                    client_price=15,
                    regular_price=10,
                    duration=service.duration,
                    is_original=True,
                    uuid=service.uuid
                )
            ],
            status=AppointmentStatus.NEW
        )
        serializer = AppointmentPreviewResponseSerializer()
        output = serializer.to_representation(instance=data)
        assert(output == {
            'stylist_uuid': str(stylist.uuid),
            'stylist_first_name': stylist.user.first_name,
            'stylist_last_name': stylist.user.last_name,
            'stylist_phone': stylist.user.phone,
            'datetime_start_at': datetime.datetime(
                2018, 1, 1, 0, 0, tzinfo=pytz.UTC
            ).astimezone(pytz.timezone(settings.TIME_ZONE)).isoformat(),
            'duration_minutes': 60,
            'status': AppointmentStatus.NEW,
            'total_tax': 4,
            'total_card_fee': 1,
            'tax_percentage': 6.5,
            'card_fee_percentage': 2.75,
            'total_client_price_before_tax': 10,
            'profile_photo_url': stylist.get_profile_photo_url(),
            'salon_name': stylist.salon.name,
            'services': [
                {
                    'uuid': str(service.uuid),
                    'service_name': service.name,
                    'service_uuid': str(service.uuid),
                    'client_price': 15,
                    'regular_price': 10,
                    'is_original': True
                }
            ],
            'grand_total': 15,
            'has_tax_included': True,
            'has_card_fee_included': False,
        })


class TestServicePricingRequestSerializer(object):
    @pytest.mark.django_db
    def test_validation(self):
        stylist: Stylist = G(Stylist)
        client: Client = G(Client)
        service: StylistService = G(StylistService, stylist=stylist)
        data = {
            'service_uuids': [str(service.uuid)]
        }

        serializer = ServicePricingRequestSerializer(data=data, context={'client': client})
        assert (serializer.is_valid(raise_exception=False))


class TestClientProfileSerializer(object):
    @pytest.mark.django_db
    def test_save_update(self):
        user: User = G(User, role=[UserRole.CLIENT, ])
        client: Client = G(Client, user=user)
        data = {
            'first_name': 'Jane',
            'last_name': 'McBob',
            'birthday': '2018-10-16',
            'zip_code': '12345',
            'email': 'client@example.com',
            'privacy': 'private'
        }

        serializer = ClientProfileSerializer(data=data, instance=user)
        assert(serializer.is_valid(raise_exception=False))
        serializer.save()
        user.refresh_from_db()
        assert(user.first_name == 'Jane')
        assert(user.last_name == 'McBob')
        assert(client.birthday == datetime.date(2018, 10, 16))
        assert(client.zip_code == '12345')
        assert(client.email == 'client@example.com')
        assert(user.email != 'client@example.com')
        assert(client.privacy == ClientPrivacy.PRIVATE)

    @pytest.mark.django_db
    def test_zipcode_update(self):
        user: User = G(User, role=[UserRole.CLIENT, ])
        client: Client = G(
            Client, user=user, zip_code='12345', last_geo_coded=timezone.now()
        )
        data = {
            'zip_code': '54321'
        }
        serializer = ClientProfileSerializer(
            data=data, instance=user, partial=True
        )
        assert (serializer.is_valid(raise_exception=False))
        serializer.save()
        client.refresh_from_db()
        assert(client.zip_code == '54321')
        assert(client.last_geo_coded is None)
