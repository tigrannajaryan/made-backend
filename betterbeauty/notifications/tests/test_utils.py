import datetime

import pytest
import pytz
from django.conf import settings
from django.utils import timezone
from django_dynamic_fixture import G
from freezegun import freeze_time
from push_notifications.models import APNSDevice, GCMDevice

from appointment.models import Appointment, AppointmentStatus
from client.models import Client
from core.models import User, UserRole
from core.types import Weekday
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
from ..utils import (
    generate_hint_to_first_book_notifications,
    generate_hint_to_rebook_notifications,
    generate_hint_to_select_stylist_notifications,
    generate_new_appointment_notification,
    generate_tomorrow_appointments_notifications,
)


@pytest.fixture
def bookable_stylist() -> Stylist:
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
    G(StylistWeekdayDiscount, weekday=1, discount_percent=10, stylist=stylist)
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
        assert (Notification.objects.count() == 0)  # client has no devices
        G(APNSDevice, user=client.user)
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
        Appointment.objects.all().delete()  # free up the slot
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
        assert(notification.code == NotificationCode.HINT_TO_SELECT_STYLIST)
        assert(notification.target == UserRole.CLIENT)
        assert(notification.pending_to_send is True)
        assert(notification.user == client.user)
        assert('We have 1 stylists' in notification.message)

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
        assert('for 5 weeks' in notification.message)
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
