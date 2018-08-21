import datetime
from typing import Dict

import pytest
import pytz

from dateutil import parser
from django_dynamic_fixture import G
from freezegun import freeze_time

from appointment.models import Appointment, AppointmentService
from appointment.types import AppointmentStatus
from client.models import ClientOfStylist
from core.types import Weekday
from salon.models import (
    Stylist,
    StylistService,
)


def stylist_appointments_data(stylist: Stylist) -> Dict[str, Appointment]:
    client = G(ClientOfStylist)
    current_appointment = G(
        Appointment, client=client, stylist=stylist,
        datetime_start_at=stylist.salon.timezone.localize(
            datetime.datetime(2018, 5, 14, 13, 20)),
    )

    past_appointment = G(
        Appointment, client=client, stylist=stylist,
        datetime_start_at=stylist.salon.timezone.localize(
            datetime.datetime(2018, 5, 14, 12, 20)),
    )

    last_week_appointment = G(
        Appointment, client=client, stylist=stylist,
        datetime_start_at=stylist.salon.timezone.localize(
            datetime.datetime(2018, 5, 7, 12, 20)),
    )

    next_week_appointment = G(
        Appointment, client=client, stylist=stylist,
        datetime_start_at=stylist.salon.timezone.localize(
            datetime.datetime(2018, 5, 21, 12, 20)),
    )

    future_appointment = G(
        Appointment, client=client, stylist=stylist,
        datetime_start_at=stylist.salon.timezone.localize(
            datetime.datetime(2018, 5, 14, 14, 20)),
    )

    late_night_appointment = G(
        Appointment, client=client, stylist=stylist,
        datetime_start_at=stylist.salon.timezone.localize(
            datetime.datetime(2018, 5, 14, 23, 50)),
    )

    next_day_appointment = G(
        Appointment, client=client, stylist=stylist,
        datetime_start_at=stylist.salon.timezone.localize(
            datetime.datetime(2018, 5, 15, 13, 20)),
    )

    appointments = {
        'current_appointment': current_appointment,
        'past_appointment': past_appointment,
        'future_appointment': future_appointment,
        'late_night_appointment': late_night_appointment,
        'next_day_appointment': next_day_appointment,
        'last_week_appointment': last_week_appointment,
        'next_week_appointment': next_week_appointment,
    }
    service = G(StylistService, stylist=stylist, duration=datetime.timedelta(minutes=60))
    for appointment in appointments.values():
        G(
            AppointmentService,
            appointment=appointment,
            duration=service.duration,
            service_name=service.name,
            service_uuid=service.uuid,
            is_original=True
        )
    return appointments


class TestStylist(object):
    @pytest.mark.django_db
    def test_get_weekday_discount_percent(self, stylist_data: Stylist):
        assert(
            stylist_data.get_weekday_discount_percent(Weekday.MONDAY) == 50
        )
        assert(
            stylist_data.get_weekday_discount_percent(Weekday.TUESDAY) == 20
        )

    @freeze_time('2018-05-14 13:30:00 UTC')
    @pytest.mark.django_db
    def test_get_today_appointments(
            self, stylist_data: Stylist,
    ):
        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)
        today_appointments = [a.id for a in stylist_data.get_today_appointments(
            upcoming_only=True,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST,
            ]
        )]

        assert(len(today_appointments) == 3)
        assert(appointments['current_appointment'].id in today_appointments)
        assert(appointments['future_appointment'].id in today_appointments)
        assert(appointments['late_night_appointment'].id in today_appointments)
        assert(appointments['next_day_appointment'].id not in today_appointments)
        assert(appointments['past_appointment'].id not in today_appointments)

        today_appointments = [
            a.id for a in stylist_data.get_today_appointments(
                upcoming_only=False,
                exclude_statuses=[
                    AppointmentStatus.CANCELLED_BY_CLIENT,
                    AppointmentStatus.CANCELLED_BY_STYLIST
                ]
            )
        ]

        assert (len(today_appointments) == 4)
        assert (appointments['current_appointment'].id in today_appointments)
        assert (appointments['past_appointment'].id in today_appointments)
        assert (appointments['future_appointment'].id in today_appointments)
        assert (appointments['late_night_appointment'].id in today_appointments)
        assert (appointments['next_day_appointment'].id not in today_appointments)

    @freeze_time('2018-05-14 13:30:00 UTC')
    @pytest.mark.django_db
    def test_get_appointments_in_datetime_range(
            self, stylist_data: Stylist,
    ):
        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)
        all_appointments = stylist_data.get_appointments_in_datetime_range()

        assert(all_appointments.count() == 7)
        appointments_from_start = stylist_data.get_appointments_in_datetime_range(
            datetime_from=None,
            datetime_to=stylist_data.get_current_now(),
            including_to=True,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST
            ]
        )
        assert(frozenset([a.id for a in appointments_from_start]) == frozenset([
            appointments['past_appointment'].id,
            appointments['current_appointment'].id,
            appointments['last_week_appointment'].id,
        ]))

        apppointmens_to_end = stylist_data.get_appointments_in_datetime_range(
            datetime_from=stylist_data.get_current_now(),
            datetime_to=None,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST
            ]
        )
        assert (frozenset([a.id for a in apppointmens_to_end]) == frozenset([
            appointments['current_appointment'].id,
            appointments['future_appointment'].id,
            appointments['late_night_appointment'].id,
            appointments['next_day_appointment'].id,
            appointments['next_week_appointment'].id,
        ]))

        appointments_between = stylist_data.get_appointments_in_datetime_range(
            datetime_from=pytz.timezone('UTC').localize(datetime.datetime(
                2018, 5, 13
            )),
            datetime_to=pytz.timezone('UTC').localize(datetime.datetime(
                2018, 5, 15, 23, 59, 59
            )),
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST
            ]
        )
        assert (frozenset([a.id for a in appointments_between]) == frozenset([
            appointments['past_appointment'].id,
            appointments['current_appointment'].id,
            appointments['future_appointment'].id,
            appointments['late_night_appointment'].id,
            appointments['next_day_appointment'].id,
        ]))

    @freeze_time('2018-05-14 13:30:00 UTC')
    @pytest.mark.django_db
    def test_set_status(self, stylist_data: Stylist):
        appointment: Appointment = G(
            Appointment, stylist=stylist_data,
            duration=datetime.timedelta()
        )
        assert(appointment.status == AppointmentStatus.NEW)

        appointment.set_status(
            AppointmentStatus.CANCELLED_BY_CLIENT, stylist_data.user
        )
        appointment.refresh_from_db()
        assert(appointment.status == AppointmentStatus.CANCELLED_BY_CLIENT)
        assert(appointment.status_history.latest('updated_at').updated_by == stylist_data.user)
        assert(appointment.status_history.latest('updated_at').updated_at ==
               stylist_data.get_current_now())


class TestStylistService(object):
    @pytest.mark.django_db
    def test_deleted_at(self):
        service = G(StylistService, duration=datetime.timedelta(), deleted_at=None)
        assert(StylistService.objects.count() == 1)
        service.deleted_at = pytz.utc.localize(datetime.datetime.now())
        service.save()
        assert (StylistService.objects.count() == 0)
        assert (StylistService.all_objects.count() == 1)


class TestAvailableSlots(object):

    @pytest.mark.django_db
    @freeze_time('2018-05-14 13:30:00 UTC')
    def test_available_slots(self, stylist_data):
        stylist = stylist_data
        date = datetime.datetime.now().date()
        stylist_appointments_data(stylist)
        stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        all_slots = stylist.get_available_slots(date)
        unavailable_slots = list(filter(lambda x: x.is_booked, all_slots))
        assert (len(unavailable_slots) == 2)
        unavailable_slot_times = list(map(lambda x: x.start, unavailable_slots))
        assert (parser.parse('2018-05-14 13:30:00+0000') in unavailable_slot_times)
        assert (parser.parse('2018-05-14 14:30:00+0000') in unavailable_slot_times)
