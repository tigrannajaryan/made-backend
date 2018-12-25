import datetime

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

from appointment.models import Appointment, AppointmentStatus
from client.models import Client
from core.models import User, UserRole
from core.types import Weekday
from core.utils.auth import custom_jwt_payload_handler
from integrations.push.types import MobileAppIdType
from notifications.models import Notification
from notifications.types import NotificationCode
from salon.models import (
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
    generate_hint_to_first_book_notifications,
    generate_hint_to_rebook_notifications,
    generate_hint_to_select_stylist_notifications,
    generate_new_appointment_notification,
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


class TestGenerateStylistCancelledAppointmentNotification(object):

    @pytest.mark.django_db
    def test_cancelled_appointment_notification(
            self, client, authorized_stylist_data
    ):
        user, auth_token = authorized_stylist_data
        client_data = G(Client)
        stylist = user.stylist

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
        stylist: Stylist = G(
            Stylist, salon=salon, created_at=PST.localize(
                datetime.datetime(2018, 12, 6, 0, 0)
            ) - datetime.timedelta(weeks=1)
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
        stylist: Stylist = G(
            Stylist, created_at=PST.localize(
                datetime.datetime(2018, 12, 6, 0, 0)
            ) - datetime.timedelta(weeks=1)
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
                Stylist, salon=salon, created_at=timezone.now() - datetime.timedelta(hours=23)
            )
            G(APNSDevice, user=stylist.user, application_id=MobileAppIdType.IOS_STYLIST_DEV)
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 0)
            stylist.created_at = timezone.now() - datetime.timedelta(hours=25)
            stylist.save()
            generate_stylist_registration_incomplete_notifications()
            assert (Notification.objects.count() == 1)
