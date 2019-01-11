import datetime
import uuid

import pytest
import pytz
from django.utils import timezone
from django_dynamic_fixture import G
from freezegun import freeze_time


from appointment.models import Appointment, AppointmentService, AppointmentStatus
from client.models import Client
from core.models import User
from core.types import Weekday
from ..models import Salon, Stylist, StylistService, StylistSpecialAvailableDate
from ..types import ClientPriceOnDate
from ..utils import (
    create_stylist_profile_for_user,
    generate_demand_list_for_stylist,
    get_current_loyalty_discount,
    get_date_with_lowest_price_on_current_week,
    get_loyalty_discount_for_week,
    get_most_popular_service
)


@freeze_time('2018-6-15 15:00')
@pytest.mark.django_db
def test_generate_demand_list_for_stylist():
    user: User = G(User)
    salon: Salon = G(Salon, timezone=pytz.utc)
    stylist = create_stylist_profile_for_user(
        user, service_time_gap=datetime.timedelta(hours=1), salon=salon
    )
    stylist.available_days.filter(
        weekday__in=[Weekday.FRIDAY, Weekday.SATURDAY, Weekday.SUNDAY]
    ).update(
        is_available=True,
        work_start_at=datetime.time(8, 0),
        work_end_at=datetime.time(12, 0)
    )
    stylist.available_days.filter(weekday=Weekday.MONDAY).update(
        is_available=False,
        work_start_at=None,
        work_end_at=None
    )
    stylist.available_days.filter(weekday=Weekday.TUESDAY).delete()
    dates = [
        datetime.date(2018, 6, 15),  # Friday - available, half loaded
        datetime.date(2018, 6, 16),  # Saturday - available, more than fully loaded
        datetime.date(2018, 6, 17),  # Sunday - available, no appointments
        datetime.date(2018, 6, 18),  # Monday - unavailable,
        datetime.date(2018, 6, 19),  # Tuesday - availability object is missing
    ]
    # 1. Create 2 appointments (2 * 1hr time gap => 2 hrs, half/day on Friday
    for i in range(0, 2):
        G(
            Appointment, stylist=stylist, created_by=stylist.user,
            datetime_start_at=stylist.with_salon_tz(datetime.datetime(2018, 6, 15, 19, 00))
        )

    # 2. Create 5 appointments (more than regular day load) on Saturday
    for i in range(0, 5):
        G(
            Appointment, stylist=stylist, created_by=stylist.user,
            datetime_start_at=stylist.with_salon_tz(datetime.datetime(2018, 6, 16, 19, 00))
        )
    demand_list = generate_demand_list_for_stylist(stylist, dates=dates)
    # pricing experiment is in effect (see description in
    # `salon.utils.generate_demand_list_for_stylist`)
    # Demand on the first 3 dates cannot be less than 0.75 / 0.5 / 0.25 respectively
    assert(demand_list[0].demand == 0.75)
    assert(demand_list[1].demand == 1)
    assert(demand_list[2].demand == 0.25)
    assert(demand_list[3].demand == 1)
    assert(demand_list[4].demand == 1)

    # 3. Test with special unavailability date
    # mark Sunday unavailable
    G(
        StylistSpecialAvailableDate,
        stylist=stylist, date=datetime.date(2018, 6, 17), is_available=False
    )
    demand_list = generate_demand_list_for_stylist(stylist, dates=dates)
    assert (demand_list[0].demand == 0.75)
    assert (demand_list[1].demand == 1)
    assert (demand_list[2].demand == 1)
    assert (demand_list[3].demand == 1)
    assert (demand_list[4].demand == 1)


@pytest.mark.django_db
def test_get_most_popular_service():
    stylist = G(Stylist)
    foreign_stylist = G(Stylist)
    existing_service_1 = G(StylistService, stylist=stylist, name='existing_1')
    existing_service_2 = G(StylistService, stylist=stylist, name='existing 2')
    deleted_service = G(
        StylistService, stylist=stylist, name='deleted', deleted_at=timezone.now()
    )
    foreign_service = G(StylistService, name='foreign')
    nowhere_service_uuid = uuid.uuid4()

    our_appointments = [Appointment.objects.create(
        stylist=stylist, datetime_start_at=timezone.now(), created_by=stylist.user
    ) for _ in range(0, 4)]
    # check correct response without services at all
    assert(get_most_popular_service(stylist) is None)
    for i in range(0, 10):
        other_appointment = Appointment.objects.create(
            stylist=foreign_stylist, datetime_start_at=timezone.now(),
            created_by=stylist.user
        )
        G(
            AppointmentService,
            service_uuid=foreign_service.uuid, appointment=other_appointment
        )
    # check that popularity is not effected by other stylist's services
    assert (get_most_popular_service(stylist) is None)
    for i in range(0, 4):
        G(AppointmentService, appointment=our_appointments[i], service_uuid=nowhere_service_uuid)
        G(AppointmentService, appointment=our_appointments[i], service_uuid=deleted_service.uuid)
    # check that deleted services are not included
    assert (get_most_popular_service(stylist) is None)
    for i in range(0, 2):
        G(
            AppointmentService,
            appointment=our_appointments[i], service_uuid=existing_service_1.uuid
        )
    assert (get_most_popular_service(stylist) == existing_service_1)
    for i in range(0, 3):
        G(
            AppointmentService,
            appointment=our_appointments[i], service_uuid=existing_service_2.uuid
        )
    assert (get_most_popular_service(stylist) == existing_service_2)


@pytest.mark.django_db
def test_get_loyalty_discount_for_week():
    stylist: Stylist = G(
        Stylist,
        rebook_within_1_week_discount_percent=10,
        rebook_within_2_weeks_discount_percent=0,
        rebook_within_3_weeks_discount_percent=30,
        rebook_within_4_weeks_discount_percent=40
    )
    assert(get_loyalty_discount_for_week(stylist, 0) == 0)
    assert(get_loyalty_discount_for_week(stylist, 1) == 10)
    assert(get_loyalty_discount_for_week(stylist, 2) == 0)
    assert(get_loyalty_discount_for_week(stylist, 3) == 30)
    assert(get_loyalty_discount_for_week(stylist, 4) == 40)
    assert(get_loyalty_discount_for_week(stylist, 5) == 0)


@pytest.mark.django_db
def test_get_current_loyalty_discount():
    stylist: Stylist = G(
        Stylist,
        rebook_within_1_week_discount_percent=40,
        rebook_within_2_weeks_discount_percent=0,
        rebook_within_3_weeks_discount_percent=0,
        rebook_within_4_weeks_discount_percent=10
    )
    client: Client = G(Client)
    discount = get_current_loyalty_discount(stylist, client)
    assert(discount.current_discount_percent == 0)
    appointment: Appointment = G(
        Appointment, status=AppointmentStatus.CHECKED_OUT, client=client, stylist=stylist,
        datetime_start_at=timezone.now() - datetime.timedelta(weeks=5)
    )
    discount = get_current_loyalty_discount(stylist, client)
    assert (discount.current_discount_percent == 0)
    # set time between 3 and 4 weeks ago
    appointment.datetime_start_at = timezone.now() - datetime.timedelta(days=25)
    appointment.save()
    discount = get_current_loyalty_discount(stylist, client)
    assert(discount is not None)
    assert(discount.current_discount_percent == 10)
    assert(discount.transitions_to_percent == 0)
    assert(discount.transitions_at == appointment.datetime_start_at + datetime.timedelta(weeks=4))
    # set time between 2 and 3 weeks ago
    appointment.datetime_start_at = timezone.now() - datetime.timedelta(days=16)
    appointment.save()
    discount = get_current_loyalty_discount(stylist, client)
    assert (discount is not None)
    assert (discount.current_discount_percent == 10)
    assert (discount.transitions_to_percent == 0)
    assert (discount.transitions_at == appointment.datetime_start_at + datetime.timedelta(weeks=4))
    # set time between 1 and 2 weeks ago
    appointment.datetime_start_at = timezone.now() - datetime.timedelta(days=16)
    appointment.save()
    discount = get_current_loyalty_discount(stylist, client)
    assert (discount.current_discount_percent == 10)
    assert (discount.transitions_to_percent == 0)
    assert (discount.transitions_at == appointment.datetime_start_at + datetime.timedelta(weeks=4))
    # set time less than a week
    appointment.datetime_start_at = timezone.now() - datetime.timedelta(days=5)
    appointment.save()
    discount = get_current_loyalty_discount(stylist, client)
    assert (discount is not None)
    assert (discount.current_discount_percent == 40)
    assert (discount.transitions_to_percent == 10)
    assert (discount.transitions_at == appointment.datetime_start_at + datetime.timedelta(weeks=1))


@pytest.mark.django_db
def test_get_date_with_lowest_price_on_current_week():
    salon = G(Salon, timezone=pytz.UTC)
    stylist = G(Stylist, salon=salon)
    with freeze_time(pytz.UTC.localize(datetime.datetime(2019, 1, 7, 12, 0))):
        week_prices = [
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 6), price=5,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 7), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 8), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 9), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 10), price=7,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 11), price=8,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 12), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 13), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
        ]
        lowest_price_date = get_date_with_lowest_price_on_current_week(
            stylist, week_prices
        )
        # there is single lowest price, and it is in the future. The price on Jan, 6
        # is the lowest in the set, but it is on a different week, so it is not counted
        assert(lowest_price_date == datetime.date(2019, 1, 10))
    with freeze_time(pytz.UTC.localize(datetime.datetime(2019, 1, 7, 12, 0))):
        week_prices = [
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 7), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 8), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 9), price=7,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 10), price=7,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 11), price=8,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 12), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 13), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
        ]
        lowest_price_date = get_date_with_lowest_price_on_current_week(
            stylist, week_prices
        )
        # there are 2 days with equally low price (7), so no date is the best
        assert(lowest_price_date is None)
    with freeze_time(pytz.UTC.localize(datetime.datetime(2019, 1, 12, 12, 0))):
        week_prices = [
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 7), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 8), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 9), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 10), price=7,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 11), price=8,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 12), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
            ClientPriceOnDate(
                date=datetime.date(2019, 1, 13), price=10,
                is_fully_booked=False, is_working_day=False, discount_type=None),
        ]
        lowest_price_date = get_date_with_lowest_price_on_current_week(
            stylist, week_prices
        )
        # the lowest price is in the past
        assert(lowest_price_date is None)
