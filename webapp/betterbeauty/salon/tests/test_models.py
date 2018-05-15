import datetime

import pytest
import pytz

from django_dynamic_fixture import G
from freezegun import freeze_time
from psycopg2.extras import DateRange

from appointment.models import Appointment
from client.models import Client
from core.models import User
from core.types import Weekday
from salon.models import (
    Salon,
    Stylist,
    StylistDateRangeDiscount,
    StylistService,
    StylistWeekdayDiscount,
)


@pytest.fixture
def stylist_data() -> Stylist:
    salon = G(
        Salon,
        name='Test salon', address='2000 Rilma Lane', city='Los Altos', state='CA',
        zip_code='94022', latitude=37.4009997, longitude=-122.1185007, timezone='UTC'
    )
    stylist_user = G(
        User,
        is_staff=False, is_superuser=False, email='test_stylist@example.com',
        first_name='Fred', last_name='McBob', phone='(650) 350-1111'
    )
    stylist = G(
        Stylist,
        salon=salon, user=stylist_user,
        work_start_at=datetime.time(8, 0), work_end_at=datetime.time(15, 0),
    )

    G(
        StylistWeekdayDiscount,
        stylist=stylist, weekday=Weekday.MONDAY, discount_percent=50)

    G(
        StylistDateRangeDiscount, stylist=stylist, discount_percent=30,
        dates=DateRange(datetime.date(2018, 4, 8), datetime.date(2018, 4, 11))

    )

    return stylist


class TestStylist(object):
    @pytest.mark.django_db
    def test_get_weekday_discount_percent(self, stylist_data: Stylist):
        assert(
            stylist_data.get_weekday_discount_percent(Weekday.MONDAY) == 50
        )
        assert(
            stylist_data.get_weekday_discount_percent(Weekday.TUESDAY) == 0
        )

    @pytest.mark.django_db
    def test_get_date_range_discount_percent(self, stylist_data: Stylist):
        assert(
            stylist_data.get_date_range_discount_percent(datetime.date(2018, 4, 9)) == 30
        )
        assert (
            stylist_data.get_date_range_discount_percent(datetime.date(2018, 4, 10)) == 30
        )
        assert (
            stylist_data.get_date_range_discount_percent(datetime.date(2018, 4, 12)) == 0
        )

    @freeze_time('2018-05-14 13:30:00 UTC')
    @pytest.mark.django_db
    def test_get_today_appointments(self, stylist_data: Stylist):
        client = G(Client)
        current_appointment = G(
            Appointment, client=client, stylist=stylist_data,
            datetime_start_at=pytz.timezone(stylist_data.salon.timezone).localize(
                datetime.datetime(2018, 5, 14, 13, 20)),
            duration=datetime.timedelta(minutes=30)
        )

        past_appointment = G(
            Appointment, client=client, stylist=stylist_data,
            datetime_start_at=pytz.timezone(stylist_data.salon.timezone).localize(
                datetime.datetime(2018, 5, 14, 12, 20)),
            duration=datetime.timedelta(minutes=30)
        )

        future_appointment = G(
            Appointment, client=client, stylist=stylist_data,
            datetime_start_at=pytz.timezone(stylist_data.salon.timezone).localize(
                datetime.datetime(2018, 5, 14, 14, 20)),
            duration=datetime.timedelta(minutes=30)
        )

        late_night_appointment = G(
            Appointment, client=client, stylist=stylist_data,
            datetime_start_at=pytz.timezone(stylist_data.salon.timezone).localize(
                datetime.datetime(2018, 5, 14, 23, 50)),
            duration=datetime.timedelta(minutes=30)
        )

        next_day_appointment = G(
            Appointment, client=client, stylist=stylist_data,
            datetime_start_at=pytz.timezone(stylist_data.salon.timezone).localize(
                datetime.datetime(2018, 5, 15, 13, 20)),
            duration=datetime.timedelta(minutes=30)
        )

        today_appointments = [a.id for a in stylist_data.get_today_appointments()]

        assert(len(today_appointments) == 3)
        assert(current_appointment.id in today_appointments)
        assert(past_appointment.id not in today_appointments)
        assert(future_appointment.id in today_appointments)
        assert(late_night_appointment.id in today_appointments)
        assert(next_day_appointment.id not in today_appointments)

        today_appointments = [
            a.id for a in stylist_data.get_today_appointments(upcoming_only=False)
        ]

        assert (len(today_appointments) == 4)
        assert (current_appointment.id in today_appointments)
        assert (past_appointment.id in today_appointments)
        assert (future_appointment.id in today_appointments)
        assert (late_night_appointment.id in today_appointments)
        assert (next_day_appointment.id not in today_appointments)


class TestStylistService(object):
    @pytest.mark.django_db
    def test_deleted_at(self):
        service = G(StylistService, duration=datetime.timedelta(), deleted_at=None)
        assert(StylistService.objects.count() == 1)
        service.deleted_at = pytz.utc.localize(datetime.datetime.now())
        service.save()
        assert (StylistService.objects.count() == 0)
        assert (StylistService.all_objects.count() == 1)
