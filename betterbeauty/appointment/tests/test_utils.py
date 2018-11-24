import datetime

import pytest
import pytz

from django_dynamic_fixture import G
from freezegun import freeze_time

from appointment.models import Appointment, AppointmentStatus
from appointment.utils import (
    appointments_to_delete_from_stylist_calendar,
    appointments_to_insert_to_stylist_calendar,
)
from salon.models import Salon, Stylist


@freeze_time('2018-11-24 10:00:00 EST')
@pytest.mark.django_db
def test_appointments_to_insert_to_stylist_calendar():
    # Eligible appointments must match the following criteria:
    # - stylist has google access token
    # - appointment is created AFTER stylist added google integration
    # - appointment is in NEW state
    # - appointment wasn't added to stylist's google calendar before
    salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
    stylist: Stylist = G(
        Stylist, salon=salon, google_access_token='access',
        google_refresh_token='refresh_token',
        google_integration_added_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 23, 0, 0)
        )
    )
    appointment_to_add_1: Appointment = G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 25, 0, 0)
        ), status=AppointmentStatus.NEW, stylist=stylist
    )
    appointment_to_add_2: Appointment = G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 25, 0, 0)
        ), status=AppointmentStatus.CHECKED_OUT, stylist=stylist
    )
    # appointment to skip because starts before google integration was added
    G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 22, 0, 0)
        ), stylist=stylist
    )
    # appointment to skip because in wrong status
    G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 22, 0, 0),
        ), stylist=stylist, status=AppointmentStatus.CANCELLED_BY_CLIENT
    )
    # appointment to skip because already added
    G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 22, 0, 0)
        ), stylist_google_calendar_id='123', stylist=stylist
    )
    eligible_appointments = appointments_to_insert_to_stylist_calendar()
    assert(frozenset([a.id for a in eligible_appointments]) == frozenset([
        appointment_to_add_1.id, appointment_to_add_2.id
    ]))


@freeze_time('2018-11-24 10:00:00 EST')
@pytest.mark.django_db
def test_appointments_to_delete_from_stylist_calendar():
    # which are in cancelled state, but still have `stylist_google_calendar_id` field set.
    salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
    stylist: Stylist = G(
        Stylist, salon=salon, google_access_token='access',
        google_refresh_token='refresh_token',
        google_integration_added_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 23, 0, 0)
        )
    )
    appointment_to_cancel_1 = G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 22, 0, 0)
        ), stylist_google_calendar_id='123', stylist=stylist,
        status=AppointmentStatus.CANCELLED_BY_CLIENT
    )
    appointment_to_cancel_2 = G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 22, 0, 0)
        ), stylist_google_calendar_id='123', stylist=stylist,
        status=AppointmentStatus.CANCELLED_BY_CLIENT
    )
    # skip because no appointment id
    G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 22, 0, 0)
        ), stylist=stylist,
        status=AppointmentStatus.CANCELLED_BY_CLIENT
    )
    # skip because wrong status
    G(
        Appointment, datetime_start_at=pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 22, 0, 0)
        ), stylist_google_calendar_id='123', stylist=stylist,
        status=AppointmentStatus.CHECKED_OUT
    )
    eligible_appointments = appointments_to_delete_from_stylist_calendar()
    assert (frozenset([a.id for a in eligible_appointments]) == frozenset([
        appointment_to_cancel_1.id, appointment_to_cancel_2.id
    ]))
