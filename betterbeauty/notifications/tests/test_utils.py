import datetime

import mock
import pytest
import pytz
from django.conf import settings
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import G
from freezegun import freeze_time
from push_notifications.models import APNSDevice, GCMDevice
from rest_framework_jwt.settings import api_settings

from api.v1.auth.utils import create_client_profile_from_phone
from api.v1.client.constants import NEW_YORK_LOCATION
from api.v1.client.serializers import AppointmentValidationMixin
from appointment.models import Appointment, AppointmentService, AppointmentStatus
from client.models import Client
from core.models import PhoneSMSCodes, User, UserRole
from core.types import Weekday
from core.utils.auth import custom_jwt_payload_handler
from integrations.push.types import MobileAppIdType
from notifications.models import Notification
from notifications.types import NotificationCode
from salon.models import (
    Invitation,
    InvitationStatus,
    PreferredStylist,
    Salon,
    Stylist,
    StylistAvailableWeekDay,
    StylistService,
    StylistSpecialAvailableDate,
    StylistWeekdayDiscount,
)
from salon.utils import create_stylist_profile_for_user
from ..utils import (
    generate_deal_of_week_notifications,
    generate_follow_up_invitation_sms,
    generate_hint_to_first_book_notifications,
    generate_hint_to_rebook_notifications,
    generate_hint_to_select_stylist_notifications,
    generate_invite_your_stylist_notifications,
    generate_new_appointment_notification,
    generate_remind_add_photo_notifications,
    generate_remind_define_discounts_notifications,
    generate_remind_define_hours_notifications,
    generate_remind_define_services_notification,
    generate_remind_invite_clients_notifications,
    generate_stylist_registration_incomplete_notifications,
    generate_tomorrow_appointments_notifications,
)


@pytest.fixture
def bookable_stylist(phone: str=None) -> Stylist:
    if phone is None:
        phone = '+15555555555'
    user = G(User, role=[UserRole.STYLIST], phone=phone)
    salon = G(Salon, timezone=pytz.timezone(settings.TIME_ZONE))
    stylist: Stylist = G(
        Stylist, user=user, salon=salon, service_time_gap=datetime.timedelta(hours=1),
        has_business_hours_set=True
    )
    G(
        StylistAvailableWeekDay, stylist=stylist, weekday=1,
        work_start_at=datetime.time(9, 0),
        work_end_at=datetime.time(10, 0),
        is_available=True
    )
    return stylist


@pytest.fixture
def busy_stylist() -> Stylist:
    """Return stylist unavailable for booking"""
    user = G(User, role=[UserRole.STYLIST], phone='+15555555555')
    salon = G(Salon, timezone=pytz.timezone(settings.TIME_ZONE))
    stylist: Stylist = G(
        Stylist, user=user, salon=salon, service_time_gap=datetime.timedelta(hours=1),
        has_business_hours_set=True
    )
    G(
        StylistAvailableWeekDay, stylist=stylist, weekday=1,
        work_start_at=datetime.time(9, 0),
        work_end_at=datetime.time(10, 0),
        is_available=True
    )
    # capture the only busy slot
    G(
        Appointment, stylist=stylist,
        datetime_start_at=datetime.datetime(
            2018, 11, 12, 9, 0, tzinfo=pytz.timezone(settings.TIME_ZONE))
    )
    # define a discount
    G(StylistService, stylist=stylist, is_enabled=True)
    return stylist


@pytest.fixture
def stylist_eligible_for_notification(stylist_created_before_days=89) -> Stylist:
    """Generate a generic stylist eligible for sending notification"""

    user: User = G(User, phone='123456')
    stylist: Stylist = G(
        Stylist, created_at=timezone.now() - datetime.timedelta(days=stylist_created_before_days),
        has_business_hours_set=True, deactivated_at=None, user=user
    )
    # another notification sent more that 24hr ago
    G(
        Notification, code='some_other_code',
        sent_at=timezone.now() - datetime.timedelta(hours=25), target=UserRole.STYLIST,
        user=user, pending_to_send=False
    )
    G(StylistService, stylist=stylist, is_enabled=True)
    G(APNSDevice, user=stylist.user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
    return stylist


@pytest.fixture
def stylist_eligible_for_invite_reminder() -> Stylist:
    """Generate a stylist perfectly eligible for REMIND_INVITE_CLIENTS notification"""
    stylist = stylist_eligible_for_notification(stylist_created_before_days=77)
    user = stylist.user
    # let there be the same notification sent > 30 days ago
    G(
        Notification, code=NotificationCode.REMIND_INVITE_CLIENTS,
        created_at=timezone.now() - datetime.timedelta(days=31), target=UserRole.STYLIST,
        user=user, pending_to_send=False
    )
    return stylist


@pytest.fixture
def stylist_eligible_for_photo_reminder() -> Stylist:
    """Generate a stylist perfectly eligible for REMIND_ADD_PHOTO notification"""
    stylist = stylist_eligible_for_notification(stylist_created_before_days=10)
    user = stylist.user
    user.photo = ''
    user.save()
    return stylist


@pytest.fixture
def stylist_eligible_for_services_reminder() -> Stylist:
    """Generate a stylist perfectly eligible for REMIND_DEFINE_SERVICES notification"""
    stylist = stylist_eligible_for_notification(stylist_created_before_days=10)
    StylistService.objects.all().delete()
    return stylist


@pytest.fixture
def stylist_eligible_for_discounts_reminder() -> Stylist:
    """Generate a stylist perfectly eligible for REMIND_DEFINE_DISCOUNTS notification"""
    stylist = stylist_eligible_for_notification(stylist_created_before_days=50)
    stylist.is_discount_configured = False
    stylist.rebook_within_1_week_discount_percent = 25
    stylist.rebook_within_2_week_discount_percent = 20
    stylist.rebook_within_3_week_discount_percent = 15
    stylist.save()
    salon = stylist.salon
    salon.location = NEW_YORK_LOCATION
    salon.save()
    ANOTHER_NYC_LOCATION: Point = Point(-74.0735302, 40.6779378, srid=4326)
    WASHINGTON_DC_LOCATION: Point = Point(-77.1546623, 38.8935128, srid=4326)
    G(PreferredStylist, stylist=stylist, client=G(Client, country=salon.country,
                                                  location=NEW_YORK_LOCATION))
    G(PreferredStylist, stylist=stylist, client=G(Client, country=salon.country,
                                                  location=ANOTHER_NYC_LOCATION))
    G(PreferredStylist, stylist=stylist, client=G(Client, country=salon.country,
                                                  location=WASHINGTON_DC_LOCATION))
    return stylist


@pytest.fixture
def stylist_eligible_for_hours_reminder() -> Stylist:
    """Generate a stylist perfectly eligible for REMIND_DEFINE_HOURS notification"""
    stylist = stylist_eligible_for_notification(stylist_created_before_days=10)
    stylist.has_business_hours_set = False
    stylist.save()
    return stylist


class TestGenerateHintToFirstBookNotification(object):

    @pytest.mark.django_db
    @freeze_time('2018-11-9 20:30:00 UTC')
    def test_bookable_stylist(self, bookable_stylist):
        client = G(Client)
        G(
            PreferredStylist, client=client, stylist=bookable_stylist,
            created_at=datetime.datetime(2018, 11, 5, 0, 0, tzinfo=pytz.UTC)
        )
        preexisting_appointment = G(
            Appointment, client=client
        )
        generate_hint_to_first_book_notifications()
        assert (Notification.objects.count() == 0)  # no services and discounts, appt exists
        G(StylistService, is_enabled=True, stylist=bookable_stylist)
        generate_hint_to_first_book_notifications()
        assert (Notification.objects.count() == 0)  # no discount, appointment exists
        G(StylistWeekdayDiscount, weekday=1, discount_percent=10, stylist=bookable_stylist)
        generate_hint_to_first_book_notifications()
        assert(Notification.objects.count() == 0)  # appointment sill exists
        preexisting_appointment.delete()
        generate_hint_to_first_book_notifications()
        assert (Notification.objects.count() == 1)
        notification: Notification = Notification.objects.last()
        assert(notification.code == NotificationCode.HINT_TO_FIRST_BOOK)
        assert(notification.target == UserRole.CLIENT)
        assert(notification.user == client.user)
        # check idempotence / presence of notifications
        generate_hint_to_first_book_notifications()
        assert (Notification.objects.count() == 1)

    @pytest.mark.django_db
    @freeze_time('2018-11-9 20:30:00 UTC')
    def test_non_bookable_stylist(self, busy_stylist):
        client = G(Client)
        G(GCMDevice, user=client.user, active=True)
        G(
            PreferredStylist, client=client, stylist=busy_stylist,
            created_at=datetime.datetime(2018, 11, 5, 0, 0, tzinfo=pytz.UTC)
        )
        generate_hint_to_first_book_notifications()
        assert (Notification.objects.count() == 0)
        G(StylistWeekdayDiscount, stylist=busy_stylist, weekday=1, discount_percent=10)
        generate_hint_to_first_book_notifications()
        assert (Notification.objects.count() == 1)


class TestGenerateHintToSelectStylistNotification(object):

    @pytest.mark.django_db
    @freeze_time('2018-11-26 20:30:00 UTC')
    def test_without_bookable_stylists(self):
        client = G(Client, created_at=pytz.UTC.localize(
            datetime.datetime(2018, 11, 20, 0, 0)))
        G(APNSDevice, user=client.user)
        assert (Notification.objects.count() == 0)
        generate_hint_to_select_stylist_notifications()
        assert(Notification.objects.count() == 0)
        stylist = bookable_stylist()
        G(StylistService, stylist=stylist, is_enabled=True)
        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 1)

    @pytest.mark.django_db
    @freeze_time('2018-11-26 20:30:00 UTC')
    def test_with_present_and_deleted_stylist(self):
        stylist: Stylist = bookable_stylist()
        another_stylist: Stylist = bookable_stylist(phone='+15555555554')
        G(StylistService, stylist=stylist, is_enabled=True)
        G(StylistService, stylist=another_stylist, is_enabled=True)
        client = G(Client, created_at=pytz.UTC.localize(
            datetime.datetime(2018, 11, 20, 0, 0)))
        G(APNSDevice, user=client.user)
        p = G(PreferredStylist, client=client, stylist=stylist)
        p.delete()
        G(PreferredStylist, client=client, stylist=another_stylist)
        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 0)

    @pytest.mark.django_db
    @freeze_time('2018-11-26 20:30:00 UTC')
    def test_with_recently_added_client(self, bookable_stylist):
        G(StylistService, stylist=bookable_stylist, is_enabled=True)
        client = G(Client, created_at=pytz.UTC.localize(
            datetime.datetime(2018, 11, 24, 0, 0)))
        G(APNSDevice, user=client.user)
        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 0)
        client.created_at = pytz.UTC.localize(
            datetime.datetime(2018, 11, 20, 0, 0))
        client.save()
        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 1)

    @pytest.mark.django_db
    @freeze_time('2018-11-26 20:30:00 UTC')
    def test_with_existing_notification(self, bookable_stylist):
        G(StylistService, stylist=bookable_stylist, is_enabled=True)
        client = G(Client, created_at=pytz.UTC.localize(
            datetime.datetime(2018, 11, 20, 0, 0)))
        G(APNSDevice, user=client.user)
        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 1)

        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 1)

    @pytest.mark.django_db
    @freeze_time('2018-11-26 20:30:00 UTC')
    def test_with_bookable_stylist(self, bookable_stylist):
        G(StylistService, stylist=bookable_stylist, is_enabled=True)
        client = G(Client, created_at=pytz.UTC.localize(
            datetime.datetime(2018, 11, 20, 0, 0)))
        G(APNSDevice, user=client.user)
        p = G(PreferredStylist, client=client, stylist=bookable_stylist)
        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 0)
        p.delete()
        generate_hint_to_select_stylist_notifications()
        assert (Notification.objects.count() == 1)
        notification: Notification = Notification.objects.last()
        assert (notification.code == NotificationCode.HINT_TO_SELECT_STYLIST)
        assert (notification.target == UserRole.CLIENT)
        assert (notification.pending_to_send is True)
        assert (notification.user == client.user)
        assert ('We have 1 stylists' in notification.message)


class TestGenerateHintToRebookNotification(object):
    @pytest.mark.django_db
    def test_verify_rebook_period(self, bookable_stylist):
        G(StylistService, stylist=bookable_stylist, is_enabled=True)
        client: Client = G(Client)
        G(APNSDevice, user=client.user)
        G(Appointment, client=client,
          datetime_start_at=timezone.now() - datetime.timedelta(weeks=5))
        generate_hint_to_rebook_notifications()
        assert(Notification.objects.count() == 1)
        notification: Notification = Notification.objects.last()
        assert('in 5 weeks' in notification.message)
        assert(notification.code == NotificationCode.HINT_TO_REBOOK)
        assert(notification.user == client.user)
        # test indempotency
        generate_hint_to_rebook_notifications()
        assert (Notification.objects.count() == 1)

    @pytest.mark.django_db
    def test_verify_no_stylists(self):
        client: Client = G(Client)
        G(APNSDevice, user=client.user)
        G(Appointment, client=client,
          datetime_start_at=timezone.now() - datetime.timedelta(weeks=5))
        generate_hint_to_rebook_notifications()
        assert (Notification.objects.count() == 0)
        G(Stylist, deactivated_at=timezone.now())
        generate_hint_to_rebook_notifications()
        assert (Notification.objects.count() == 0)
        G(Stylist)
        generate_hint_to_rebook_notifications()
        assert (Notification.objects.count() == 0)

    @pytest.mark.django_db
    def test_verify_no_previous_bookings(self, bookable_stylist):
        G(StylistService, stylist=bookable_stylist, is_enabled=True)
        client: Client = G(Client)
        G(APNSDevice, user=client.user)
        generate_hint_to_rebook_notifications()
        assert (Notification.objects.count() == 0)
        # try with recent booking
        G(Appointment, client=client,
          datetime_start_at=timezone.now() - datetime.timedelta(weeks=5))
        recent_booking: Appointment = G(
            Appointment, client=client,
            datetime_start_at=timezone.now() - datetime.timedelta(weeks=2))
        generate_hint_to_rebook_notifications()
        assert (Notification.objects.count() == 0)
        recent_booking.status = AppointmentStatus.CANCELLED_BY_CLIENT
        recent_booking.save(update_fields=['status', ])
        generate_hint_to_rebook_notifications()
        assert (Notification.objects.count() == 1)


@pytest.fixture
def new_appointment_stylist_client():
    salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
    stylist: Stylist = G(Stylist, salon=salon)
    G(APNSDevice, user=stylist.user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
    G(
        StylistAvailableWeekDay, weekday=Weekday.TUESDAY,
        work_start_at=datetime.time(9, 0),
        work_end_at=datetime.time(12, 0), stylist=stylist,
        is_available=True
    )
    G(
        StylistAvailableWeekDay, weekday=Weekday.WEDNESDAY,
        work_start_at=datetime.time(9, 35),
        work_end_at=datetime.time(12, 0), stylist=stylist,
        is_available=True
    )
    client: Client = G(Client)
    return stylist, client


@pytest.fixture()
def authorized_stylist_data(db):
    salon = G(
        Salon,
        name='Test salon', address='2000, Rilma Lane, Los Altos, US 94022',
        city='Los Altos', state='CA',
        zip_code='94022', location=Point(x=-122.1185007, y=37.4009997), country='US',
        timezone=pytz.utc
    )
    stylist_user = G(
        User,
        is_staff=False, is_superuser=False, email='test_stylist@example.com',
        first_name='Fred', last_name='McBob', phone='(650) 350-1111'
    )
    stylist: Stylist = create_stylist_profile_for_user(
        stylist_user,
        salon=salon,
        service_time_gap=datetime.timedelta(minutes=30)
    )
    monday_discount = stylist.get_or_create_weekday_discount(
        weekday=Weekday.MONDAY
    )
    monday_discount.discount_percent = 50
    monday_discount.save()
    G(APNSDevice, user=stylist_user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
    jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER
    payload = custom_jwt_payload_handler(stylist_user, role=UserRole.STYLIST)
    token = jwt_encode_handler(payload)
    auth_token = 'Token {0}'.format(token)
    return stylist_user, auth_token


@pytest.fixture()
def authorized_client_data(client):
    user = create_client_profile_from_phone('+19876543210')
    code = PhoneSMSCodes.create_or_update_phone_sms_code('+19876543210')
    auth_url = reverse('api:v1:auth:verify-code')
    data = client.post(
        auth_url, data={
            'phone': '+19876543210',
            'code': code.code,
        }
    ).data
    G(APNSDevice, user=user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
    token = data['token']
    auth_token = 'Token {0}'.format(token)
    return user, auth_token


class TestGenerateStylistCancelledAppointmentNotification(object):

    @pytest.mark.django_db
    def test_stylist_cancelled_appointment_notification(
            self, client, authorized_stylist_data
    ):
        user, auth_token = authorized_stylist_data
        client_data = G(Client)
        stylist = user.stylist
        G(APNSDevice, user=client_data.user, application_id=MobileAppIdType.IOS_CLIENT_DEV)

        # deliver at appointment_start_time-30min
        # (appointment_start_time-30min is earlier than next 10am)
        with freeze_time('2018-12-4 7:30 UTC'):
            our_appointment = G(
                Appointment,
                status=AppointmentStatus.NEW,
                stylist=stylist,
                client=client_data,
                duration=datetime.timedelta(0),
                datetime_start_at=datetime.datetime(2018, 12, 4, 9, 0, tzinfo=pytz.UTC),
                created_by=client_data.user
            )

            url = reverse(
                'api:v1:stylist:appointment', kwargs={'appointment_uuid': our_appointment.uuid}
            )
            data = {'status': AppointmentStatus.CANCELLED_BY_STYLIST}
            client.post(url, HTTP_AUTHORIZATION=auth_token, data=data)

            notification: Notification = Notification.objects.order_by('created_at').last()
            assert (notification.send_time_window_start == datetime.time(8, 30))
            assert (notification.send_time_window_end == datetime.time.max)

        # Test send (immediately since current time in [10am..8pm] in client’s timezone)
        with freeze_time('2018-12-4 10:30 UTC'):
            our_appointment = G(
                Appointment,
                status=AppointmentStatus.NEW,
                stylist=stylist,
                client=client_data,
                duration=datetime.timedelta(0),
                datetime_start_at=datetime.datetime(2018, 12, 4, 12, 0, tzinfo=pytz.UTC),
                created_by=client_data.user
            )

            url = reverse(
                'api:v1:stylist:appointment', kwargs={'appointment_uuid': our_appointment.uuid}
            )
            data = {'status': AppointmentStatus.CANCELLED_BY_STYLIST}
            client.post(url, HTTP_AUTHORIZATION=auth_token, data=data)

            notification: Notification = Notification.objects.order_by('created_at').last()
            assert (notification.send_time_window_start == datetime.time(10, 30))
            assert (notification.send_time_window_end == datetime.time.max)
        # Test delay until next 10 AM
        with freeze_time('2018-12-4 22:00 UTC'):
            our_appointment = G(
                Appointment,
                status=AppointmentStatus.NEW,
                stylist=stylist,
                client=client_data,
                duration=datetime.timedelta(0),
                datetime_start_at=datetime.datetime(2018, 12, 5, 11, 0, tzinfo=pytz.UTC),
                created_by=client_data.user
            )

            url = reverse(
                'api:v1:stylist:appointment', kwargs={'appointment_uuid': our_appointment.uuid}
            )
            data = {'status': AppointmentStatus.CANCELLED_BY_STYLIST}
            client.post(url, HTTP_AUTHORIZATION=auth_token, data=data)

            notification: Notification = Notification.objects.order_by('created_at').last()
            assert (notification.send_time_window_start == datetime.time(10, 00))
            assert (notification.send_time_window_end == datetime.time(20, 0, 0))


class TestGenerateClientCancelledAppointmentNotification(object):

    @pytest.mark.django_db
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_datetime_start_at', lambda s, a: a)
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_services', lambda s, a: a)
    def test_client_cancelled_appointment_notification(
            self, client, authorized_client_data, authorized_stylist_data
    ):
        client_user, auth_token = authorized_client_data
        client_data = client_user.client
        stylist_user, stylist_token = authorized_stylist_data
        stylist = stylist_user.stylist
        service_1: StylistService = G(StylistService, stylist=stylist)

        # deliver at appointment_start_time-30min
        # (appointment_start_time-30min is earlier than next 10am)
        with freeze_time('2018-12-4 7:30 UTC'):
            our_appointment = G(
                Appointment,
                status=AppointmentStatus.NEW,
                stylist=stylist,
                client=client_data,
                duration=datetime.timedelta(0),
                datetime_start_at=datetime.datetime(2018, 12, 4, 9, 0, tzinfo=pytz.UTC),
                created_by=client_data.user
            )
            G(AppointmentService, appointment=our_appointment, service=service_1)

            url = reverse(
                'api:v1:client:appointment', kwargs={'uuid': our_appointment.uuid}
            )

            data = {'status': AppointmentStatus.CANCELLED_BY_CLIENT}
            client.post(
                url, data=data, HTTP_AUTHORIZATION=auth_token,
            )

            notification: Notification = Notification.objects.order_by('created_at').last()
            assert (notification.send_time_window_start == datetime.time(8, 30))
            assert (notification.send_time_window_end == datetime.time.max)

        # Test send (immediately since current time in [10am..8pm] in client’s timezone)
        with freeze_time('2018-12-4 10:30 UTC'):
            our_appointment = G(
                Appointment,
                status=AppointmentStatus.NEW,
                stylist=stylist,
                client=client_data,
                duration=datetime.timedelta(0),
                datetime_start_at=datetime.datetime(2018, 12, 4, 12, 0, tzinfo=pytz.UTC),
                created_by=client_data.user
            )
            G(AppointmentService, appointment=our_appointment, service=service_1)

            url = reverse(
                'api:v1:client:appointment', kwargs={'uuid': our_appointment.uuid}
            )
            data = {'status': AppointmentStatus.CANCELLED_BY_CLIENT}
            client.post(url, HTTP_AUTHORIZATION=auth_token, data=data)

            notification: Notification = Notification.objects.order_by('created_at').last()
            assert (notification.send_time_window_start == datetime.time(10, 30))
            assert (notification.send_time_window_end == datetime.time.max)
        # Test delay until next 10 AM
        with freeze_time('2018-12-4 22:00 UTC'):
            our_appointment = G(
                Appointment,
                status=AppointmentStatus.NEW,
                stylist=stylist,
                client=client_data,
                duration=datetime.timedelta(0),
                datetime_start_at=datetime.datetime(2018, 12, 5, 11, 0, tzinfo=pytz.UTC),
                created_by=client_data.user
            )
            G(AppointmentService, appointment=our_appointment, service=service_1)

            url = reverse(
                'api:v1:client:appointment', kwargs={'uuid': our_appointment.uuid}
            )
            data = {'status': AppointmentStatus.CANCELLED_BY_CLIENT}
            client.post(url, HTTP_AUTHORIZATION=auth_token, data=data)

            notification: Notification = Notification.objects.order_by('created_at').last()
            assert (notification.send_time_window_start == datetime.time(10, 00))
            assert (notification.send_time_window_end == datetime.time.max)


class TestGenerateNewAppointmentNotification(object):
    @pytest.mark.django_db
    def test_time_window_before_working_day_same_day(
            self, new_appointment_stylist_client
    ):
        stylist, client = new_appointment_stylist_client
        appointment: Appointment = G(
            Appointment, stylist=stylist, client=client,
            datetime_start_at=pytz.timezone('America/New_York').localize(
                datetime.datetime(2018, 12, 4, 10, 00)
            ), created_by=client.user
        )
        # appointment is created before start of work day, for the same day
        # window should be min(day_start - 30 minutes, 10am), but at least 15
        # minutes later after creation
        with freeze_time('2018-12-4 7:30 EST'):
            assert(generate_new_appointment_notification(appointment) == 1)
            notification: Notification = Notification.objects.last()
            assert(
                notification.send_time_window_start == datetime.time(8, 30)
            )
            Notification.objects.all().delete()
        with freeze_time('2018-12-4 9:20 EST'):
            assert(generate_new_appointment_notification(appointment) == 1)
            notification: Notification = Notification.objects.last()
            assert(
                notification.send_time_window_start == datetime.time(9, 35)
            )
            Notification.objects.all().delete()
        with freeze_time('2018-12-4 9:45 EST'):
            assert(generate_new_appointment_notification(appointment) == 1)
            notification: Notification = Notification.objects.last()
            assert(
                notification.send_time_window_start == datetime.time(10, 0)
            )
            Notification.objects.all().delete()

    @pytest.mark.django_db
    def test_time_window_during_working_day_same_day(self, new_appointment_stylist_client):
        stylist, client = new_appointment_stylist_client
        appointment: Appointment = G(
            Appointment, stylist=stylist, client=client,
            datetime_start_at=pytz.timezone('America/New_York').localize(
                datetime.datetime(2018, 12, 4, 11, 00)
            ), created_by=client.user
        )
        # appointment is created during the work day, for the same day
        # window should be min(day_start - 30 minutes, 10am), but at least 15
        # minutes later after creation
        with freeze_time('2018-12-4 10:00 EST'):
            assert (generate_new_appointment_notification(appointment) == 1)
            notification: Notification = Notification.objects.last()
            assert (
                notification.send_time_window_start == datetime.time(10, 15)
            )
            Notification.objects.all().delete()

    @pytest.mark.django_db
    def test_time_window_during_working_day_next_day(self, new_appointment_stylist_client):
        stylist, client = new_appointment_stylist_client
        appointment: Appointment = G(
            Appointment, stylist=stylist, client=client,
            datetime_start_at=pytz.timezone('America/New_York').localize(
                datetime.datetime(2018, 12, 5, 11, 00)
            ), created_by=client.user
        )
        # appointment is created during the work day, for the same day
        # window should be min(day_start - 30 minutes, 10am), but at least 15
        # minutes later after creation
        with freeze_time('2018-12-4 10:00 EST'):
            assert (generate_new_appointment_notification(appointment) == 1)
            notification: Notification = Notification.objects.last()
            assert (
                notification.send_time_window_start == datetime.time(10, 15)
            )

    @pytest.mark.django_db
    def test_time_window_right_before_midnight_for_next_day(
            self, new_appointment_stylist_client):
        stylist, client = new_appointment_stylist_client
        appointment: Appointment = G(
            Appointment, stylist=stylist, client=client,
            datetime_start_at=pytz.timezone('America/New_York').localize(
                datetime.datetime(2018, 12, 5, 11, 00)
            ), created_by=client.user
        )
        # earliest time we can send notification is after midnight, which is
        # outside of current time window. So we should set new time window
        # for tomorrow
        with freeze_time('2018-12-4 23:55 EST'):
            assert (generate_new_appointment_notification(appointment) == 1)
            notification: Notification = Notification.objects.last()
            assert (
                notification.send_time_window_start == datetime.time(9, 5)
            )  # 30 minutes before tomorrow day starts
            assert (
                notification.send_time_window_end == datetime.time(23, 54)
            )


class TestGenerateTomorrowAppointmentsNotifications(object):
    @pytest.mark.django_db
    def test_time_of_generation_on_working_day(self):
        salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist = G(Stylist, salon=salon)
        G(
            APNSDevice, user=stylist.user,
            application_id=MobileAppIdType.IOS_STYLIST_DEV
        )
        G(
            StylistAvailableWeekDay, weekday=Weekday.THURSDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(18, 0),
            is_available=True, stylist=stylist
        )
        G(
            Appointment,
            stylist=stylist,
            datetime_start_at=pytz.UTC.localize(datetime.datetime(
                2018, 12, 7, 17, 0  # noon EST
            ))
        )
        with freeze_time('2018-12-6 18:29 EST'):
            generate_tomorrow_appointments_notifications()
            assert(Notification.objects.all().count() == 0)
        with freeze_time('2018-12-6 18:31 EST'):
            generate_tomorrow_appointments_notifications()
            assert(Notification.objects.all().count() == 1)
            # test indempotence
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 1)
        notification: Notification = Notification.objects.last()
        assert(notification.user == stylist.user)
        assert(notification.code == NotificationCode.TOMORROW_APPOINTMENTS)
        assert(notification.data == {'date': datetime.date(2018, 12, 7).isoformat()})
        assert(notification.send_time_window_start == datetime.time(18, 31))
        assert(notification.send_time_window_end == datetime.time(23, 59, 59))
        assert(notification.discard_after == salon.timezone.localize(
            datetime.datetime(
                2018, 12, 7, 0, 0
            )
        ))
        assert(notification.target == UserRole.STYLIST)

    @pytest.mark.django_db
    def test_time_of_generation_on_non_working_day(self):
        salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist = G(Stylist, salon=salon)
        G(
            APNSDevice, user=stylist.user,
            application_id=MobileAppIdType.IOS_STYLIST_DEV
        )
        G(
            Appointment,
            stylist=stylist,
            datetime_start_at=pytz.UTC.localize(datetime.datetime(
                2018, 12, 7, 17, 0  # noon EST
            ))
        )
        # test non-working day
        with freeze_time('2018-12-6 19:29 EST'):
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 0)
        with freeze_time('2018-12-6 19:31 EST'):
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 1)
            # test indempotence
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 1)
        # test special availability
        Notification.objects.all().delete()
        G(
            StylistAvailableWeekDay, weekday=Weekday.THURSDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(18, 0),
            is_available=True, stylist=stylist
        )
        G(
            StylistSpecialAvailableDate, stylist=stylist,
            date=datetime.date(2018, 12, 6), is_available=False
        )
        with freeze_time('2018-12-6 19:29 EST'):
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 0)
        with freeze_time('2018-12-6 19:31 EST'):
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 1)
            # test indempotence
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 1)

    @pytest.mark.django_db
    def test_generation_with_no_appointments(self):
        salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist = G(Stylist, salon=salon)
        G(
            APNSDevice, user=stylist.user,
            application_id=MobileAppIdType.IOS_STYLIST_DEV
        )
        G(
            StylistAvailableWeekDay, weekday=Weekday.THURSDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(18, 0),
            is_available=True, stylist=stylist
        )
        with freeze_time('2018-12-6 18:31 EST'):
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 0)

            appointment: Appointment = G(
                Appointment,
                stylist=stylist,
                datetime_start_at=pytz.UTC.localize(datetime.datetime(
                    2018, 12, 7, 17, 0  # noon EST
                )), status=AppointmentStatus.CHECKED_OUT
            )
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 0)
            appointment.status = AppointmentStatus.NEW
            appointment.save()
            generate_tomorrow_appointments_notifications()
            assert (Notification.objects.all().count() == 1)


class TestGenerateStylistRegistrationIncompleteNotifications(object):
    @pytest.mark.django_db
    def test_time_of_day_with_salon(self):
        PST = pytz.timezone('America/Los_Angeles')
        salon: Salon = G(Salon, timezone=PST)
        user = G(User, phone='1234')
        stylist: Stylist = G(
            Stylist, salon=salon, created_at=PST.localize(
                datetime.datetime(2018, 12, 6, 0, 0)
            ) - datetime.timedelta(weeks=1), user=user
        )
        G(APNSDevice, user=stylist.user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 18, 1))):
            # verify it won't send today if time > 18:01
            generate_stylist_registration_incomplete_notifications()
            assert(Notification.objects.count() == 0)
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 7, 2, 1))):
            # verify it will still send next day
            generate_stylist_registration_incomplete_notifications()
            assert(Notification.objects.count() == 1)
            Notification.objects.all().delete()
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 17, 59))):
            generate_stylist_registration_incomplete_notifications()
            assert(Notification.objects.count() == 1)
            Notification.objects.all().delete()
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 10, 0))):
            generate_stylist_registration_incomplete_notifications()
            assert(Notification.objects.count() == 1)
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 1)
            notification: Notification = Notification.objects.last()
            assert(notification.send_time_window_start == datetime.time(11, 0))
            assert(notification.send_time_window_end == datetime.time(18, 0))
            assert(notification.send_time_window_tz == PST)
            assert(notification.target == UserRole.STYLIST)
            assert(notification.user == stylist.user)

    @pytest.mark.django_db
    def test_time_of_day_without_salon(self):
        PST = pytz.timezone('America/Los_Angeles')
        user = G(User, phone='1234')
        stylist: Stylist = G(
            Stylist, created_at=PST.localize(
                datetime.datetime(2018, 12, 6, 0, 0)
            ) - datetime.timedelta(weeks=1), user=user
        )
        G(APNSDevice, user=stylist.user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
        # now test without salon; it should now default to EST timezone (PST + 3)
        # we'll pretend as if we're in PST to see if it behaves correctly with
        # different timezone
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 18, 1))):
            generate_stylist_registration_incomplete_notifications()
            assert(Notification.objects.count() == 0)
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 17, 59))):
            generate_stylist_registration_incomplete_notifications()
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 14, 59))):
            # now it's 17:59 in EST, so should work
            generate_stylist_registration_incomplete_notifications()
            assert(Notification.objects.count() == 1)
            Notification.objects.all().delete()
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 10, 0))):
            generate_stylist_registration_incomplete_notifications()
            assert(Notification.objects.count() == 1)
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 1)
            notification: Notification = Notification.objects.last()
            assert(notification.send_time_window_start == datetime.time(11, 0))
            assert(notification.send_time_window_end == datetime.time(18, 0))
            assert(notification.send_time_window_tz == pytz.timezone('America/New_York'))
            assert(notification.target == UserRole.STYLIST)
            assert(notification.user == stylist.user)

    @pytest.mark.django_db
    def test_incompleteness_criteria(self):
        PST = pytz.timezone('America/Los_Angeles')
        salon: Salon = G(Salon, timezone=PST)
        user: User = G(User, phone='123123')
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 17, 59))):
            stylist: Stylist = G(
                Stylist, salon=salon, created_at=timezone.now() - datetime.timedelta(weeks=1),
                user=user
            )
            G(APNSDevice, user=stylist.user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 1)
            Notification.objects.all().delete()
            stylist.has_business_hours_set = True
            stylist.save()
            G(StylistService, is_enabled=True, stylist=stylist)
            # now stylist has phone, business hours and an enabled service
            # which is considered as profile-complete
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 0)

    @pytest.mark.django_db
    def test_registration_time(self):
        PST = pytz.timezone('America/Los_Angeles')
        salon: Salon = G(Salon, timezone=PST)
        with freeze_time(PST.localize(datetime.datetime(2018, 12, 6, 17, 59))):
            stylist: Stylist = G(
                Stylist, salon=salon, created_at=timezone.now() - datetime.timedelta(hours=23),
                user=G(User, phone='1234')
            )
            G(APNSDevice, user=stylist.user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 0)
            stylist.created_at = timezone.now() - datetime.timedelta(hours=25)
            stylist.save()
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 0)
            stylist.created_at = timezone.now() - datetime.timedelta(hours=73)
            stylist.save()
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 1)


class TestGenerateRemindInviteClientsNotifications(object):
    @pytest.mark.django_db
    def test_positive_path(self, stylist_eligible_for_invite_reminder: Stylist):
        assert(Notification.objects.count() == 2)
        assert(generate_remind_invite_clients_notifications() == 1)
        assert (Notification.objects.count() == 3)
        notification: Notification = Notification.objects.last()
        assert(notification.code == NotificationCode.REMIND_INVITE_CLIENTS)
        assert(notification.target == UserRole.STYLIST)
        assert(notification.user == stylist_eligible_for_invite_reminder.user)
        assert(notification.send_time_window_start == datetime.time(10, 0))
        assert(notification.send_time_window_end == datetime.time(20, 0))

    @pytest.mark.django_db
    def test_with_pending_notifications(self, stylist_eligible_for_invite_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST, user=stylist_eligible_for_invite_reminder.user,
            code='whatever', pending_to_send=True, sent_at=None
        )
        assert (generate_remind_invite_clients_notifications() == 0)

    @pytest.mark.django_db
    def test_recent_notifications(self, stylist_eligible_for_invite_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST, user=stylist_eligible_for_invite_reminder.user,
            code='whatever', pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(
                hours=23
            )
        )
        assert (generate_remind_invite_clients_notifications() == 0)

    @pytest.mark.django_db
    def test_with_existing_recent_notifications(self, stylist_eligible_for_invite_reminder):
        G(
            Notification, target=UserRole.STYLIST, user=stylist_eligible_for_invite_reminder.user,
            code=NotificationCode.REMIND_INVITE_CLIENTS,
            pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(days=29)
        )
        assert (generate_remind_invite_clients_notifications() == 0)

    @pytest.mark.django_db
    def test_partial_profile(self, stylist_eligible_for_invite_reminder: Stylist):
        user = stylist_eligible_for_invite_reminder.user
        user.phone = None
        user.save()
        assert(stylist_eligible_for_invite_reminder.is_profile_bookable is False)
        assert (generate_remind_invite_clients_notifications() == 0)

    @pytest.mark.django_db
    def test_non_recent_or_very_recent_stylist(self,
                                               stylist_eligible_for_invite_reminder: Stylist):
        stylist_eligible_for_invite_reminder.created_at = timezone.now() - datetime.timedelta(
            days=91
        )
        stylist_eligible_for_invite_reminder.save()
        assert (generate_remind_invite_clients_notifications() == 0)

        stylist_eligible_for_invite_reminder.created_at = timezone.now() - datetime.timedelta(
            hours=20
        )
        stylist_eligible_for_invite_reminder.save()
        assert (generate_remind_invite_clients_notifications() == 0)

    @pytest.mark.django_db
    def test_stylist_with_invitations(self, stylist_eligible_for_invite_reminder: Stylist):
        G(Invitation, stylist=stylist_eligible_for_invite_reminder)
        assert (generate_remind_invite_clients_notifications() == 0)


class TestGenerateRemindAddPhotoNotifications(object):
    @pytest.mark.django_db
    def test_positive_path(self, stylist_eligible_for_photo_reminder: Stylist):
        assert(Notification.objects.count() == 1)
        assert(generate_remind_add_photo_notifications() == 1)
        assert (Notification.objects.count() == 2)
        notification: Notification = Notification.objects.last()
        assert(notification.code == NotificationCode.REMIND_ADD_PHOTO)
        assert(notification.target == UserRole.STYLIST)
        assert(notification.user == stylist_eligible_for_photo_reminder.user)
        assert(notification.send_time_window_start == datetime.time(10, 0))
        assert(notification.send_time_window_end == datetime.time(20, 0))

    @pytest.mark.django_db
    def test_with_pending_notifications(self, stylist_eligible_for_photo_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST, user=stylist_eligible_for_photo_reminder.user,
            code='whatever', pending_to_send=True, sent_at=None
        )
        assert (generate_remind_add_photo_notifications() == 0)

    @pytest.mark.django_db
    def test_recent_notifications(self, stylist_eligible_for_photo_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST, user=stylist_eligible_for_photo_reminder.user,
            code='whatever', pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(
                hours=23
            )
        )
        assert (generate_remind_add_photo_notifications() == 0)

    @pytest.mark.django_db
    def test_with_add_photo_notifications(self, stylist_eligible_for_invite_reminder):
        G(
            Notification, target=UserRole.STYLIST, user=stylist_eligible_for_invite_reminder.user,
            code=NotificationCode.REMIND_ADD_PHOTO,
            pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(days=29)
        )
        assert (generate_remind_add_photo_notifications() == 0)

    @pytest.mark.django_db
    def test_partial_profile(self, stylist_eligible_for_photo_reminder: Stylist):
        user = stylist_eligible_for_photo_reminder.user
        user.phone = None
        user.save()
        assert(stylist_eligible_for_photo_reminder.is_profile_bookable is False)
        assert (generate_remind_add_photo_notifications() == 0)

    @pytest.mark.django_db
    def test_non_recent__or_very_recent_stylist(self,
                                                stylist_eligible_for_photo_reminder: Stylist):
        stylist_eligible_for_photo_reminder.created_at = timezone.now() - datetime.timedelta(
            days=61
        )
        stylist_eligible_for_photo_reminder.save()
        assert (generate_remind_add_photo_notifications() == 0)

        stylist_eligible_for_photo_reminder.created_at = timezone.now() - datetime.timedelta(
            hours=20
        )
        stylist_eligible_for_photo_reminder.save()
        assert (generate_remind_add_photo_notifications() == 0)

    @pytest.mark.django_db
    def test_stylist_with_photo(self, stylist_eligible_for_photo_reminder: Stylist):
        user = stylist_eligible_for_photo_reminder.user
        dummy_user = G(User)
        user.photo = dummy_user.photo
        user.save()
        assert (generate_remind_add_photo_notifications() == 0)


class TestGenerateRemindDefineServiceNotifications(object):

    @pytest.mark.django_db
    def test_positive_path(self, stylist_eligible_for_services_reminder: Stylist):
        assert (Notification.objects.count() == 1)
        assert (generate_remind_define_services_notification() == 1)
        assert (Notification.objects.count() == 2)
        notification: Notification = Notification.objects.last()
        assert (notification.code == NotificationCode.REMIND_DEFINE_SERVICES)
        assert (notification.target == UserRole.STYLIST)
        assert (notification.user == stylist_eligible_for_services_reminder.user)
        assert (notification.send_time_window_start == datetime.time(10, 0))
        assert (notification.send_time_window_end == datetime.time(20, 0))

    @pytest.mark.django_db
    def test_with_pending_notifications(self, stylist_eligible_for_services_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_services_reminder.user,
            code='whatever', pending_to_send=True, sent_at=None
        )
        assert (generate_remind_define_services_notification() == 0)

    @pytest.mark.django_db
    def test_recent_notifications(self, stylist_eligible_for_services_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_services_reminder.user,
            code='whatever', pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(
                hours=23
            )
        )
        assert (generate_remind_define_services_notification() == 0)

    @pytest.mark.django_db
    def test_with_remind_define_service_notifications(self,
                                                      stylist_eligible_for_services_reminder):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_services_reminder.user,
            code=NotificationCode.REMIND_DEFINE_SERVICES,
            pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(days=25)
        )
        assert (generate_remind_define_services_notification() == 0)

    @pytest.mark.django_db
    def test_partial_profile(self, stylist_eligible_for_services_reminder: Stylist):
        user = stylist_eligible_for_services_reminder.user
        user.phone = None
        user.save()
        assert (stylist_eligible_for_services_reminder.is_profile_bookable is False)
        assert (generate_remind_define_services_notification() == 0)

    @pytest.mark.django_db
    def test_non_recent__or_very_recent_stylist(self,
                                                stylist_eligible_for_services_reminder: Stylist):
        stylist_eligible_for_services_reminder.created_at = timezone.now() - datetime.timedelta(
            days=32
        )
        stylist_eligible_for_services_reminder.save()
        assert (generate_remind_define_services_notification() == 0)

        stylist_eligible_for_services_reminder.created_at = timezone.now() - datetime.timedelta(
            hours=20
        )
        stylist_eligible_for_services_reminder.save()
        assert (generate_remind_define_services_notification() == 0)

    @pytest.mark.django_db
    def test_stylist_with_service(self, stylist_eligible_for_services_reminder: Stylist):
        G(StylistService, stylist=stylist_eligible_for_services_reminder, is_enabled=True)
        assert (generate_remind_define_services_notification() == 0)


class TestGenerateRemindDefineDiscountsNotifications(object):

    @pytest.mark.django_db
    def test_positive_path(self, stylist_eligible_for_discounts_reminder: Stylist):
        assert (Notification.objects.count() == 1)
        assert (generate_remind_define_discounts_notifications() == 1)
        assert (Notification.objects.count() == 2)
        notification: Notification = Notification.objects.last()
        assert (notification.code == NotificationCode.REMIND_DEFINE_DISCOUNTS)
        assert (notification.target == UserRole.STYLIST)
        print(notification.message)
        assert (notification.message.startswith('2 '))
        assert (notification.user == stylist_eligible_for_discounts_reminder.user)
        assert (notification.send_time_window_start == datetime.time(10, 0))
        assert (notification.send_time_window_end == datetime.time(20, 0))

    @pytest.mark.django_db
    def test_with_pending_notifications(self, stylist_eligible_for_discounts_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_discounts_reminder.user,
            code='whatever', pending_to_send=True, sent_at=None
        )
        assert (generate_remind_define_discounts_notifications() == 0)

    @pytest.mark.django_db
    def test_recent_notifications(self, stylist_eligible_for_discounts_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_discounts_reminder.user,
            code='whatever', pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(
                hours=23
            )
        )
        assert (generate_remind_define_discounts_notifications() == 0)

    @pytest.mark.django_db
    def test_with_remind_define_discounts_notifications(self,
                                                        stylist_eligible_for_discounts_reminder):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_discounts_reminder.user,
            code=NotificationCode.REMIND_DEFINE_DISCOUNTS,
            pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(days=25)
        )
        assert (generate_remind_define_discounts_notifications() == 0)

    @pytest.mark.django_db
    def test_partial_profile(self, stylist_eligible_for_discounts_reminder: Stylist):
        user = stylist_eligible_for_discounts_reminder.user
        user.phone = None
        user.save()
        assert (stylist_eligible_for_discounts_reminder.is_profile_bookable is False)
        assert (generate_remind_define_discounts_notifications() == 0)

    @pytest.mark.django_db
    def test_non_recent_or_very_recent_stylist(self,
                                               stylist_eligible_for_discounts_reminder: Stylist):
        stylist_eligible_for_discounts_reminder.created_at = timezone.now() - datetime.timedelta(
            days=92
        )
        stylist_eligible_for_discounts_reminder.save()
        assert (generate_remind_define_discounts_notifications() == 0)
        stylist_eligible_for_discounts_reminder.created_at = timezone.now() - datetime.timedelta(
            hours=20
        )
        stylist_eligible_for_discounts_reminder.save()
        assert (generate_remind_define_discounts_notifications() == 0)

    @pytest.mark.django_db
    def test_stylist_with_discount(self, stylist_eligible_for_discounts_reminder: Stylist):
        stylist_eligible_for_discounts_reminder.is_discount_configured = True
        stylist_eligible_for_discounts_reminder.save()
        assert (generate_remind_define_discounts_notifications() == 0)


class TestGenerateFollowUpInvitationSms(object):
    @pytest.mark.django_db
    @mock.patch('notifications.utils.send_sms_message')
    @freeze_time('2018-12-31 23:30 UTC')  # 6:30pm EST
    def test_positive_path_invitation(self, sms_mock):
        invitation: Invitation = G(
            Invitation, status=InvitationStatus.INVITED, created_client=None,
            created_at=timezone.now() - datetime.timedelta(days=15),
            followup_sent_at=None, followup_count=0
        )
        assert(generate_follow_up_invitation_sms() == 1)
        invitation.refresh_from_db()
        assert(invitation.followup_count == 1)
        assert(invitation.followup_sent_at == timezone.now())
        assert(sms_mock.call_count == 1)

    @pytest.mark.django_db
    @mock.patch('notifications.utils.send_sms_message')
    @freeze_time('2018-12-31 23:30 UTC')  # 6:30pm EST
    def test_positive_path_invitation_stylist_invites_client(self, sms_mock):
        user: User = G(User, first_name='Fred', last_name='McBob')
        stylist: Stylist = G(Stylist, user=user)
        invitation: Invitation = G(
            Invitation, status=InvitationStatus.INVITED, created_client=None,
            created_at=timezone.now() - datetime.timedelta(days=15),
            followup_sent_at=None, followup_count=0, stylist=stylist,
            invited_by_client=None
        )
        assert (generate_follow_up_invitation_sms() == 1)
        invitation.refresh_from_db()
        assert (invitation.followup_count == 1)
        assert (invitation.followup_sent_at == timezone.now())
        assert (sms_mock.call_count == 1)
        assert ('you book with Fred there.' in sms_mock.call_args[1]['body'])

    @pytest.mark.django_db
    @mock.patch('notifications.utils.send_sms_message')
    @freeze_time('2018-12-31 23:30 UTC')  # 6:30pm EST
    def test_positive_path_invitation_client_invites_client(self, sms_mock):
        user: User = G(User, first_name='Jenny', last_name='McBob')
        inviting_client: Client = G(Client, user=user)
        invitation: Invitation = G(
            Invitation, status=InvitationStatus.INVITED, created_client=None,
            created_at=timezone.now() - datetime.timedelta(days=15),
            followup_sent_at=None, followup_count=0, invited_by_client=inviting_client,
            stylist=None
        )
        assert (generate_follow_up_invitation_sms() == 1)
        invitation.refresh_from_db()
        assert (invitation.followup_count == 1)
        assert (invitation.followup_sent_at == timezone.now())
        assert (sms_mock.call_count == 1)
        assert ('Jenny' in sms_mock.call_args[1]['body'])
        assert ('McBob' not in sms_mock.call_args[1]['body'])
        assert ('you book there.' in sms_mock.call_args[1]['body'])

    @pytest.mark.django_db
    @mock.patch('notifications.utils.send_sms_message')
    @freeze_time('2018-12-31 23:30 UTC')  # 6:30pm EST
    def test_recent_invitation(self, sms_mock):
        invitation: Invitation = G(
            Invitation, status=InvitationStatus.INVITED, created_client=None,
            created_at=timezone.now() - datetime.timedelta(days=13),
            followup_sent_at=None, followup_count=0
        )
        assert (generate_follow_up_invitation_sms() == 0)
        invitation.refresh_from_db()
        assert (invitation.followup_count == 0)
        assert (invitation.followup_sent_at is None)
        assert (sms_mock.call_count == 0)

    @pytest.mark.django_db
    @mock.patch('notifications.utils.send_sms_message')
    @freeze_time('2018-12-31 23:30 UTC')  # 6:30pm EST
    def test_already_resent_invitation(self, sms_mock):
        invitation: Invitation = G(
            Invitation, status=InvitationStatus.INVITED, created_client=None,
            created_at=timezone.now() - datetime.timedelta(days=15),
            followup_sent_at=None, followup_count=0
        )
        assert (generate_follow_up_invitation_sms() == 1)
        invitation.refresh_from_db()
        assert (invitation.followup_count == 1)
        assert (invitation.followup_sent_at == timezone.now())
        assert (sms_mock.call_count == 1)
        sms_mock.reset_mock()

        assert (generate_follow_up_invitation_sms() == 0)
        assert (sms_mock.call_count == 0)

    @pytest.mark.django_db
    @mock.patch('notifications.utils.send_sms_message')
    @freeze_time('2018-12-31 23:30 UTC')  # 6:30pm EST
    def test_declined_invitation(self, sms_mock):
        G(
            Invitation, status=InvitationStatus.DECLINED, created_client=None,
            created_at=timezone.now() - datetime.timedelta(days=15),
            followup_sent_at=None, followup_count=0
        )
        assert (generate_follow_up_invitation_sms() == 0)
        assert (sms_mock.call_count == 0)

    @pytest.mark.django_db
    @mock.patch('notifications.utils.send_sms_message')
    @freeze_time('2018-12-31 23:30 UTC')  # 6:30pm EST
    def test_accepted_invitation(self, sms_mock):
        G(
            Invitation, status=InvitationStatus.ACCEPTED, created_client=G(Client),
            created_at=timezone.now() - datetime.timedelta(days=15),
            followup_sent_at=None, followup_count=0
        )
        assert (generate_follow_up_invitation_sms() == 0)
        assert (sms_mock.call_count == 0)


class TestGenerateRemindDefineHoursNotifications(object):

    @pytest.mark.django_db
    def test_positive_path(self, stylist_eligible_for_hours_reminder: Stylist):
        assert (Notification.objects.count() == 1)
        assert (generate_remind_define_hours_notifications() == 1)
        assert (Notification.objects.count() == 2)
        notification: Notification = Notification.objects.last()
        assert (notification.code == NotificationCode.REMIND_DEFINE_HOURS)
        assert (notification.target == UserRole.STYLIST)
        assert (notification.user == stylist_eligible_for_hours_reminder.user)
        assert (notification.send_time_window_start == datetime.time(10, 0))
        assert (notification.send_time_window_end == datetime.time(20, 0))

    @pytest.mark.django_db
    def test_with_pending_notifications(self, stylist_eligible_for_hours_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_hours_reminder.user,
            code='whatever', pending_to_send=True, sent_at=None
        )
        assert (generate_remind_define_hours_notifications() == 0)

    @pytest.mark.django_db
    def test_recent_notifications(self, stylist_eligible_for_hours_reminder: Stylist):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_hours_reminder.user,
            code='whatever', pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(
                hours=23
            )
        )
        assert (generate_remind_define_hours_notifications() == 0)

    @pytest.mark.django_db
    def test_with_remind_define_hours_notifications(self,
                                                    stylist_eligible_for_hours_reminder):
        G(
            Notification, target=UserRole.STYLIST,
            user=stylist_eligible_for_hours_reminder.user,
            code=NotificationCode.REMIND_DEFINE_HOURS,
            pending_to_send=False, sent_at=timezone.now() - datetime.timedelta(days=25)
        )
        assert (generate_remind_define_hours_notifications() == 0)

    @pytest.mark.django_db
    def test_partial_profile(self, stylist_eligible_for_hours_reminder: Stylist):
        user = stylist_eligible_for_hours_reminder.user
        user.phone = None
        user.save()
        assert (stylist_eligible_for_hours_reminder.is_profile_bookable is False)
        assert (generate_remind_define_hours_notifications() == 0)

    @pytest.mark.django_db
    def test_non_recent_or_very_recent_stylist(self,
                                               stylist_eligible_for_hours_reminder: Stylist):
        stylist_eligible_for_hours_reminder.created_at = timezone.now() - datetime.timedelta(
            days=32
        )
        stylist_eligible_for_hours_reminder.save()
        assert (generate_remind_define_hours_notifications() == 0)

        stylist_eligible_for_hours_reminder.created_at = timezone.now() - datetime.timedelta(
            hours=20
        )
        stylist_eligible_for_hours_reminder.save()
        assert (generate_remind_define_hours_notifications() == 0)

    @pytest.mark.django_db
    def test_stylist_with_business_hours_set(self, stylist_eligible_for_hours_reminder: Stylist):
        stylist_eligible_for_hours_reminder.has_business_hours_set = True
        stylist_eligible_for_hours_reminder.save()
        assert (generate_remind_define_hours_notifications() == 0)


class TestGenerateDealOfWeekNotification(object):
    @freeze_time('2019-1-21 12:00:00 UTC')
    @pytest.mark.django_db
    def test_positive_path(self):
        user1: User = G(User, phone='123')
        user2: User = G(User, phone='345')
        salon1: Salon = G(Salon, timezone=pytz.UTC, location=Point(-73.9734388, 40.7718351))
        salon2: Salon = G(Salon, timezone=pytz.UTC, location=Point(-72, 40.65))
        stylist1: Stylist = G(Stylist, salon=salon1, user=user1, has_business_hours_set=True)
        G(StylistService, stylist=stylist1, is_enabled=True)
        stylist2: Stylist = G(Stylist, salon=salon2, user=user2, has_business_hours_set=True)
        G(StylistService, stylist=stylist2, is_enabled=True)
        client1 = G(Client, location=Point(-73.972282, 40.7724047))
        client2 = G(Client, location=Point(-73.972282, 40.7724047))
        G(PreferredStylist, stylist=stylist1, client=client1)
        G(PreferredStylist, stylist=stylist2, client=client2)
        G(StylistAvailableWeekDay, stylist=stylist1, weekday=Weekday.WEDNESDAY, is_available=True)
        G(StylistAvailableWeekDay, stylist=stylist2, weekday=Weekday.WEDNESDAY, is_available=True)
        G(
            StylistWeekdayDiscount,
            weekday=Weekday.WEDNESDAY,
            stylist=stylist1, discount_percent=30, is_deal_of_week=True
        )
        G(
            StylistWeekdayDiscount,
            weekday=Weekday.WEDNESDAY,
            stylist=stylist2, discount_percent=30, is_deal_of_week=True
        )
        result = generate_deal_of_week_notifications()
        assert(result == 1)
        notification: Notification = Notification.objects.last()
        assert(notification.user == client1.user)
        assert(notification.code == NotificationCode.DEAL_OF_THE_WEEK)
        assert('Wednesday' in notification.message)
        assert(stylist1.user.first_name in notification.message)
        assert('30%' in notification.message)
        result = generate_deal_of_week_notifications()
        assert (result == 0)

    @freeze_time('2019-1-21 12:00:00 UTC')
    @pytest.mark.django_db
    def test_existing_deal_notification(self):
        user1: User = G(User, phone='123')
        salon1: Salon = G(Salon, timezone=pytz.UTC, location=Point(-73.9734388, 40.7718351))
        stylist1: Stylist = G(Stylist, salon=salon1, user=user1, has_business_hours_set=True)
        G(StylistService, stylist=stylist1, is_enabled=True)
        client1 = G(Client, location=Point(-73.972282, 40.7724047))
        G(PreferredStylist, stylist=stylist1, client=client1)
        G(
            StylistWeekdayDiscount,
            weekday=Weekday.WEDNESDAY,
            stylist=stylist1, discount_percent=30, is_deal_of_week=True
        )
        G(StylistAvailableWeekDay, stylist=stylist1, weekday=Weekday.WEDNESDAY, is_available=True)
        existing_notification: Notification = G(
            Notification,
            code=NotificationCode.DEAL_OF_THE_WEEK,
            target=UserRole.CLIENT,
            user=client1.user,
            created_at=timezone.now() - datetime.timedelta(weeks=3)
        )
        result = generate_deal_of_week_notifications()
        assert (result == 0)
        existing_notification.created_at = timezone.now() - datetime.timedelta(days=29)
        existing_notification.save()
        result = generate_deal_of_week_notifications()
        assert (result == 1)

    @freeze_time('2019-1-21 12:00:00 UTC')
    @pytest.mark.django_db
    def test_existing_different_notification(self):
        user1: User = G(User, phone='123')
        salon1: Salon = G(Salon, timezone=pytz.UTC, location=Point(-73.9734388, 40.7718351))
        stylist1: Stylist = G(Stylist, salon=salon1, user=user1, has_business_hours_set=True)
        G(StylistService, stylist=stylist1, is_enabled=True)
        client1 = G(Client, location=Point(-73.972282, 40.7724047))
        G(PreferredStylist, stylist=stylist1, client=client1)
        G(
            StylistWeekdayDiscount,
            weekday=Weekday.WEDNESDAY,
            stylist=stylist1, discount_percent=30, is_deal_of_week=True
        )
        G(StylistAvailableWeekDay, stylist=stylist1, weekday=Weekday.WEDNESDAY, is_available=True)
        existing_notification: Notification = G(
            Notification,
            code=NotificationCode.REMIND_ADD_PHOTO,
            target=UserRole.CLIENT,
            user=client1.user,
            created_at=timezone.now() - datetime.timedelta(hours=20)
        )
        result = generate_deal_of_week_notifications()
        assert (result == 0)
        existing_notification.created_at = timezone.now() - datetime.timedelta(hours=29)
        existing_notification.save()
        result = generate_deal_of_week_notifications()
        assert (result == 1)

    @freeze_time('2019-1-21 12:00:00 UTC')
    @pytest.mark.django_db
    def test_non_working_day_on_deal_date(self):
        user1: User = G(User, phone='123')
        salon1: Salon = G(Salon, timezone=pytz.UTC, location=Point(-73.9734388, 40.7718351))
        stylist1: Stylist = G(Stylist, salon=salon1, user=user1, has_business_hours_set=True)
        G(StylistService, stylist=stylist1, is_enabled=True)
        client1 = G(Client, location=Point(-73.972282, 40.7724047))
        G(PreferredStylist, stylist=stylist1, client=client1)
        G(
            StylistWeekdayDiscount,
            weekday=Weekday.WEDNESDAY,
            stylist=stylist1, discount_percent=30, is_deal_of_week=True
        )
        non_working_day = G(
            StylistAvailableWeekDay, weekday=Weekday.WEDNESDAY, stylist=stylist1,
            is_available=False
        )
        result = generate_deal_of_week_notifications()
        assert (result == 0)
        non_working_day.is_available = True
        non_working_day.save()
        result = generate_deal_of_week_notifications()
        assert (result == 1)


class TestGenerateInviteYourStylistNotification(object):
    @pytest.mark.django_db
    def test_positive_path(self):
        client: Client = G(
            Client, created_at=timezone.now() - datetime.timedelta(days=80)
        )
        G(APNSDevice, user=client.user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert(result == 1)
        notification: Notification = Notification.objects.last()
        assert(notification.code == NotificationCode.INVITE_YOUR_STYLIST)
        assert(notification.target == UserRole.CLIENT)
        assert(notification.user == client.user)

    @pytest.mark.django_db
    def test_prior_notification_with_same_code(self):
        client: Client = G(
            Client, created_at=timezone.now() - datetime.timedelta(days=80)
        )
        G(APNSDevice, user=client.user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
        prior_notification: Notification = G(
            Notification,
            target=UserRole.CLIENT,
            user=client.user,
            code=NotificationCode.INVITE_YOUR_STYLIST,
            created_at=timezone.now() - datetime.timedelta(weeks=3)
        )
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert (result == 0)
        prior_notification.created_at = timezone.now() - datetime.timedelta(weeks=5)
        prior_notification.save()
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert (result == 1)

    @pytest.mark.django_db
    def test_prior_notification_with_different_code(self):
        client: Client = G(
            Client, created_at=timezone.now() - datetime.timedelta(days=80)
        )
        G(APNSDevice, user=client.user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
        prior_notification: Notification = G(
            Notification,
            target=UserRole.CLIENT,
            user=client.user,
            code='some_code',
            created_at=timezone.now() - datetime.timedelta(hours=23)
        )
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert (result == 0)
        prior_notification.created_at = timezone.now() - datetime.timedelta(hours=25)
        prior_notification.save()
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert (result == 1)

    @pytest.mark.django_db
    def test_already_has_or_had_preferred_stylist(self):
        client: Client = G(
            Client, created_at=timezone.now() - datetime.timedelta(days=80)
        )
        G(APNSDevice, user=client.user, application_id=MobileAppIdType.IOS_CLIENT_DEV)
        stylist: Stylist = G(Stylist)
        preferred_stylist: PreferredStylist = G(
            PreferredStylist, client=client, stylist=stylist, deleted_at=None
        )
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert (result == 0)
        preferred_stylist.deleted_at = timezone.now()
        preferred_stylist.save()
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert (result == 0)
        preferred_stylist.hard_delete()
        result = generate_invite_your_stylist_notifications(dry_run=False)
        assert (result == 1)
