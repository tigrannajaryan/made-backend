import datetime

import pytest
import pytz
from django.conf import settings
from django_dynamic_fixture import G
from freezegun import freeze_time
from push_notifications.models import APNSDevice, GCMDevice

from appointment.models import Appointment
from client.models import Client
from core.models import User, UserRole
from notifications.models import Notification
from notifications.types import NotificationCode
from salon.models import (
    PreferredStylist,
    Salon,
    Stylist,
    StylistAvailableWeekDay,
    StylistService,
    StylistWeekdayDiscount,
)
from ..utils import (
    generate_hint_to_first_book_notifications,
    generate_hint_to_select_stylist_notifications,
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
