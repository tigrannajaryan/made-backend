import datetime
import uuid

import pytest
import pytz
from django.utils import timezone
from django_dynamic_fixture import G
from freezegun import freeze_time


from appointment.models import Appointment, AppointmentService
from core.models import User
from core.types import Weekday
from ..models import Salon, Stylist, StylistService
from ..utils import (
    create_stylist_profile_for_user,
    generate_demand_list_for_stylist,
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
    assert(demand_list[0].demand == 0.5)
    assert(demand_list[1].demand == 1)
    assert(demand_list[2].demand == 0)
    assert(demand_list[3].demand == 1)
    assert(demand_list[4].demand == 1)


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
