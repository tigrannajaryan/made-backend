import datetime
from typing import Dict

import pytest
import pytz
from django_dynamic_fixture import G
from freezegun import freeze_time

from api.v1.auth.utils import create_client_profile_from_phone
from appointment.models import Appointment
from appointment.types import AppointmentStatus
from client.models import Client
from core.models import User, USER_ROLE
from salon.tests.test_models import (
    stylist_appointments_data,
)


class TestClient(object):
    @freeze_time('2018-05-14 13:30:00 UTC')
    @pytest.mark.django_db
    def test_get_appointments_in_datetime_range(
            self, stylist_data
    ):
        user = G(
            User,
            is_staff=False, is_superuser=False, email='test_client@example.com',
            first_name='Fred', last_name='McBob', phone='+11234567890',
            role=[USER_ROLE.client],
        )
        client_user = create_client_profile_from_phone(phone='+11234567890', user=user)
        client: Client = client_user.client

        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)

        for a in appointments.values():
            a.real_client = client
            a.save(update_fields=['real_client', ])

        all_appointments = client.get_appointments_in_datetime_range()

        assert(all_appointments.count() == 7)
        appointments_from_start = client.get_appointments_in_datetime_range(
            datetime_from=None,
            datetime_to=stylist_data.get_current_now(),
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

        apppointmens_to_end = client.get_appointments_in_datetime_range(
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

        appointments_between = client.get_appointments_in_datetime_range(
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

        appointments['future_appointment'].real_client = G(
            Client
        )
        appointments['future_appointment'].save()

        appointments_between = client.get_appointments_in_datetime_range(
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
            appointments['late_night_appointment'].id,
            appointments['next_day_appointment'].id,
        ]))
