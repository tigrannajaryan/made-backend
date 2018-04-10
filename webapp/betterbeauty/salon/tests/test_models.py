import datetime
import pytest

from psycopg2.extras import DateRange

from django_dynamic_fixture import G

from core.models import User
from core.types import Weekday
from salon.models import (
    Stylist,
    Salon,
    StylistDateRangeDiscount,
    StylistFirstTimeBookDiscount,
    StylistWeekdayDiscount,
)


@pytest.fixture
def stylist_data() -> Stylist:
    salon = G(
        Salon,
        name='Test salon', address='2000 Rilma Lane', city='Los Altos', state='CA',
        zip_code='94022', latitude=37.4009997, longitude=-122.1185007
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
        StylistFirstTimeBookDiscount, stylist=stylist, discount_percent=40
    )

    G(
        StylistDateRangeDiscount, stylist=stylist, discount_percent=30,
        dates=DateRange(datetime.date(2018, 4, 8), datetime.date(2018, 4, 10))

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
    def test_get_first_time_discount_percent(self, stylist_data: Stylist):
        assert(
            stylist_data.get_first_time_discount_percent() == 40
        )

    @pytest.mark.django_db
    def get_date_range_discount_percent(self, stylist_data: Stylist):
        assert(
            stylist_data.get_date_range_discount_percent(datetime.date(2018, 4, 9)) == 30
        )
        assert (
            stylist_data.get_date_range_discount_percent(datetime.date(2018, 4, 10)) == 30
        )
        assert (
            stylist_data.get_date_range_discount_percent(datetime.date(2018, 4, 12)) == 30
        )
