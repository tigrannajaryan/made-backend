import datetime
from typing import Dict, List

import pytest
import pytz

from dateutil import parser
from django.utils import timezone
from django_dynamic_fixture import G
from freezegun import freeze_time

from appointment.models import Appointment, AppointmentService
from appointment.types import AppointmentStatus
from client.models import Client, PreferredStylist
from core.models import User, UserRole
from core.types import Weekday
from salon.models import (
    Salon,
    Stylist,
    StylistAvailableWeekDay,
    StylistService,
    StylistSpecialAvailableDate,
)
from salon.types import TimeSlot


def stylist_appointments_data(stylist: Stylist) -> Dict[str, Appointment]:
    client = G(Client)
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

    @pytest.mark.django_db
    def test_get_preferred_clients(self):
        stylist: Stylist = G(Stylist)
        our_client = G(Client)
        # foreign client
        G(Client)
        assert(stylist.get_preferred_clients().count() == 0)
        preferred_stylist: PreferredStylist = G(
            PreferredStylist, client=our_client, stylist=stylist
        )
        assert(stylist.get_preferred_clients().count() == 1)
        assert(stylist.get_preferred_clients()[0] == our_client)
        preferred_stylist.deleted_at = timezone.now()
        preferred_stylist.save(update_fields=['deleted_at'])
        assert (stylist.get_preferred_clients().count() == 0)

    @pytest.mark.django_db
    def test_is_working_time(self):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        user: User = G(User, role=[UserRole.STYLIST, ])
        stylist: Stylist = G(Stylist, salon=salon, user=user)
        G(
            StylistAvailableWeekDay, stylist=stylist,
            weekday=Weekday.MONDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(17, 0),
            is_available=True

        )
        G(
            StylistAvailableWeekDay, stylist=stylist,
            weekday=Weekday.TUESDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(17, 0),
            is_available=False

        )
        G(
            StylistAvailableWeekDay, stylist=stylist,
            weekday=Weekday.THURSDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(17, 0),
            is_available=True

        )
        G(
            StylistSpecialAvailableDate, stylist=stylist,
            date=datetime.date(2018, 11, 29), is_available=False
        )
        est = pytz.timezone('America/New_York')
        # Monday
        assert(
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 26, 8, 59))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 26, 9, 00))) is True
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 26, 9, 1))) is True
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 26, 16, 59))) is True
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 26, 17, 1))) is False
        )
        # Tuesday
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 8, 59))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 9, 00))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 9, 1))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 16, 59))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 17, 1))) is False
        )
        # Thursday - because it's a special date
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 8, 59))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 9, 00))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 9, 1))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 16, 59))) is False
        )
        assert (
            stylist.is_working_time(est.localize(datetime.datetime(2018, 11, 27, 17, 1))) is False
        )

    @pytest.mark.django_db
    def test_is_working_day(self):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        user: User = G(User, role=[UserRole.STYLIST, ])
        stylist: Stylist = G(Stylist, salon=salon, user=user)
        G(
            StylistAvailableWeekDay, stylist=stylist,
            weekday=Weekday.MONDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(17, 0),
            is_available=True

        )
        G(
            StylistAvailableWeekDay, stylist=stylist,
            weekday=Weekday.TUESDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(17, 0),
            is_available=False

        )
        G(
            StylistAvailableWeekDay, stylist=stylist,
            weekday=Weekday.THURSDAY,
            work_start_at=datetime.time(9, 0),
            work_end_at=datetime.time(17, 0),
            is_available=True

        )
        G(
            StylistSpecialAvailableDate, stylist=stylist,
            date=datetime.date(2018, 11, 29), is_available=False
        )
        est = pytz.timezone('America/New_York')
        # Monday
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 26, 8, 59))) is True
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 26, 9, 00))) is True
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 26, 9, 1))) is True
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 26, 16, 59))) is True
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 26, 17, 1))) is True
        )
        # Tuesday
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 8, 59))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 9, 00))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 9, 1))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 16, 59))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 17, 1))) is False
        )
        # Thursday - because it's a special date
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 8, 59))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 9, 00))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 9, 1))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 16, 59))) is False
        )
        assert (
            stylist.is_working_day(est.localize(datetime.datetime(2018, 11, 27, 17, 1))) is False
        )


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
    @freeze_time('2018-05-14 07:30:00 UTC')
    def test_available_slots(self, stylist_data):
        stylist = stylist_data
        date = datetime.datetime.now().date()
        stylist_appointments_data(stylist)
        stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        all_slots = stylist.get_available_slots(date)
        unavailable_slots = list(filter(lambda x: x.is_booked, all_slots))
        assert (len(unavailable_slots) == 3)
        unavailable_slot_times = list(map(lambda x: x.start, unavailable_slots))
        assert (parser.parse('2018-05-14 12:30:00+0000') in unavailable_slot_times)
        assert (parser.parse('2018-05-14 13:30:00+0000') in unavailable_slot_times)
        assert (parser.parse('2018-05-14 14:30:00+0000') in unavailable_slot_times)

    @pytest.mark.django_db
    @freeze_time('2018-05-14 07:30:00 UTC')
    def test_available_slots_with_special_date(self, stylist_data):
        stylist: Stylist = stylist_data
        date = datetime.datetime.now().date()
        stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        G(
            StylistSpecialAvailableDate, stylist=stylist,
            date=datetime.date(2018, 5, 14), is_available=False
        )
        all_slots = stylist.get_available_slots(date)
        assert(len(all_slots) == 0)


class TestGetAvailableTime():

    @pytest.mark.django_db
    def test_demand_in_timeslot_after_endtime(self, stylist_data):
        stylist_data.available_days.filter(
            weekday=1).update(
            work_start_at=datetime.time(9, 0, 0),
            work_end_at=datetime.time(11, 1, 0),
            is_available=True)
        stylist_available_weekday = stylist_data.available_days.get(weekday=1)
        assert (stylist_available_weekday.get_available_time() == datetime.timedelta(
            hours=2, minutes=30))

        stylist_data.available_days.filter(
            weekday=2).update(work_start_at=datetime.time(9, 0, 0),
                              work_end_at=datetime.time(11, 0, 0),
                              is_available=True)
        stylist_available_weekday2 = stylist_data.available_days.get(weekday=2)
        assert (stylist_available_weekday2.get_available_time() == datetime.timedelta(
            hours=2, minutes=00))


class TestStylistAvailableWeekDay(object):
    @pytest.mark.django_db
    def test_get_slot_end_time(self):
        stylist: Stylist = G(
            Stylist, service_time_gap=datetime.timedelta(minutes=40))
        available_weekday: StylistAvailableWeekDay = G(
            StylistAvailableWeekDay,
            stylist=stylist, weekday=Weekday.MONDAY,
            work_start_at=datetime.time(10, 0),
            work_end_at=datetime.time(18, 0), is_available=True
        )
        assert (
            available_weekday.get_slot_end_time() == datetime.time(18, 40)
        )
        available_weekday.is_available = False
        available_weekday.save()
        assert (available_weekday.get_slot_end_time() is None)

    @pytest.mark.django_db
    def test_get_available_time(self):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist: Stylist = G(
            Stylist, salon=salon, service_time_gap=datetime.timedelta(minutes=30))
        available_weekday: StylistAvailableWeekDay = G(
            StylistAvailableWeekDay,
            stylist=stylist, weekday=Weekday.MONDAY,
            work_start_at=datetime.time(10, 0),
            work_end_at=datetime.time(18, 0), is_available=True
        )
        # 16 slots between 10am and 6pm
        assert(
            available_weekday.get_available_time() == datetime.timedelta(minutes=16 * 30)
        )

    @pytest.mark.django_db
    def test_get_all_slots(self):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist: Stylist = G(
            Stylist, salon=salon, service_time_gap=datetime.timedelta(minutes=30))
        available_weekday: StylistAvailableWeekDay = G(
            StylistAvailableWeekDay,
            stylist=stylist, weekday=Weekday.MONDAY,
            work_start_at=datetime.time(10, 0),
            work_end_at=datetime.time(18, 0), is_available=True
        )

        all_slots: List[TimeSlot] = available_weekday.get_all_slots()
        # 16 slots between 10am and 6pm
        assert(len(all_slots) == 16)
        first_slot_start, first_slot_end = all_slots[0]
        assert (first_slot_start == datetime.time(10, 0))
        assert (first_slot_end == datetime.time(10, 30))
        last_slot_start, last_slot_end = all_slots[-1]
        assert (last_slot_start == datetime.time(17, 30))
        assert (last_slot_end == datetime.time(18, 0))

        slots_slightly_after_noon: List[TimeSlot] = available_weekday.get_all_slots(
            current_time=datetime.time(12, 20)
        )
        # 12:30-13:00, 13:00-13:30, 13:30-14:00, 14:00-14:30, 14:30-15:00, 15:00-15-30,
        # 15:30-16:00, 16:00-16:30, 16:30-17:00, 17:00-17:30, 17:30-18:00
        # total 11 slots
        assert (len(slots_slightly_after_noon) == 11)
        first_slot_start, first_slot_end = slots_slightly_after_noon[0]
        assert(first_slot_start == datetime.time(12, 30))
        assert (first_slot_end == datetime.time(13, 0))
        last_slot_start, last_slot_end = slots_slightly_after_noon[-1]
        assert (last_slot_start == datetime.time(17, 30))
        assert (last_slot_end == datetime.time(18, 0))

        # test with special date
        special_date = datetime.date(2018, 11, 26)  # Monday
        G(StylistSpecialAvailableDate, date=special_date, stylist=stylist, is_available=False)
        special_date_slots: List[TimeSlot] = available_weekday.get_all_slots(
            for_date=special_date
        )
        assert(len(special_date_slots) == 0)
