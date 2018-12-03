import datetime

import mock
import pytest
import pytz
from django_dynamic_fixture import G
from freezegun import freeze_time

from appointment.models import Appointment, AppointmentStatus
from client.models import Client
from salon.models import Salon, Stylist


class TestAppointment(object):
    @pytest.mark.django_db
    @freeze_time('2018-11-24 10:00:00 EST')
    @mock.patch('appointment.models.build_oauth_http_object_from_tokens')
    @mock.patch('appointment.models.create_calendar_event')
    def test_create_stylist_google_calendar_event(self, create_mock, build_http_mock):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist: Stylist = G(Stylist, salon=salon)
        appointment: Appointment = G(
            Appointment, status=AppointmentStatus.CANCELLED_BY_CLIENT,
            stylist=stylist, stylist_google_calendar_id='some_id'
        )
        appointment.create_stylist_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        create_mock.return_value = 'new_event_id'
        stylist.google_access_token = 'access_token'
        stylist.google_refresh_token = 'refresh_token'
        stylist.google_integration_added_at = pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 23, 0, 0)
        )
        stylist.save()
        appointment.create_stylist_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        appointment.create_stylist_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        appointment.stylist_google_calendar_id = None
        appointment.save()
        appointment.create_stylist_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        appointment.status = AppointmentStatus.NEW
        appointment.save()
        appointment.create_stylist_google_calendar_event()
        build_http_mock.assert_called_once_with(
            access_token=stylist.google_access_token,
            refresh_token=stylist.google_refresh_token,
            model_object_to_update=stylist,
            access_token_field='google_access_token'
        )
        assert(create_mock.call_count == 1)
        assert(create_mock.call_args[1]['start_at'] == appointment.datetime_start_at)
        assert(
            create_mock.call_args[1]['end_at'] ==
            appointment.datetime_start_at + appointment.stylist.service_time_gap)
        appointment.refresh_from_db()
        assert(appointment.stylist_google_calendar_id == 'new_event_id')

    @pytest.mark.django_db
    @freeze_time('2018-11-24 10:00:00 EST')
    @mock.patch('appointment.models.build_oauth_http_object_from_tokens')
    @mock.patch('appointment.models.cancel_calendar_event')
    def test_cancel_stylist_google_calendar_event(self, cancel_mock, build_http_mock):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist: Stylist = G(
            Stylist, salon=salon, google_access_token='access_token',
            google_refresh_token='refresh_token'
        )
        appointment: Appointment = G(
            Appointment, status=AppointmentStatus.NEW,
            stylist=stylist, stylist_google_calendar_id='some_id'
        )
        appointment.cancel_stylist_google_calendar_event()
        build_http_mock.assert_not_called()
        cancel_mock.assert_not_called()
        appointment.status = AppointmentStatus.CANCELLED_BY_CLIENT
        appointment.save()

        appointment.cancel_stylist_google_calendar_event()
        build_http_mock.assert_called_once_with(
            access_token=stylist.google_access_token,
            refresh_token=stylist.google_refresh_token,
            model_object_to_update=stylist,
            access_token_field='google_access_token'
        )
        assert(cancel_mock.call_count == 1)
        assert (cancel_mock.call_args[1]['event_id'] == 'some_id')

    @pytest.mark.django_db
    @freeze_time('2018-11-24 10:00:00 EST')
    @mock.patch('appointment.models.build_oauth_http_object_from_tokens')
    @mock.patch('appointment.models.create_calendar_event')
    def test_create_client_google_calendar_event(self, create_mock, build_http_mock):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist = G(Stylist, salon=salon)
        client: Client = G(Client)
        appointment: Appointment = G(
            Appointment, status=AppointmentStatus.CANCELLED_BY_CLIENT,
            stylist=stylist, stylist_google_calendar_id='some_id',
            client=client
        )
        appointment.create_client_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        create_mock.return_value = 'new_event_id'
        client.google_access_token = 'access_token'
        client.google_refresh_token = 'refresh_token'
        client.google_integration_added_at = pytz.timezone('America/New_York').localize(
            datetime.datetime(2018, 11, 23, 0, 0)
        )
        client.save()
        appointment.create_client_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        appointment.create_client_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        appointment.client_google_calendar_id = None
        appointment.save()
        appointment.create_client_google_calendar_event()
        build_http_mock.assert_not_called()
        create_mock.assert_not_called()
        appointment.status = AppointmentStatus.NEW
        appointment.save()
        appointment.create_client_google_calendar_event()
        build_http_mock.assert_called_once_with(
            access_token=client.google_access_token,
            refresh_token=client.google_refresh_token,
            model_object_to_update=client,
            access_token_field='google_access_token'
        )
        assert(create_mock.call_count == 1)
        assert(create_mock.call_args[1]['start_at'] == appointment.datetime_start_at)
        assert(
            create_mock.call_args[1]['end_at'] ==
            appointment.datetime_start_at + appointment.stylist.service_time_gap)
        appointment.refresh_from_db()
        assert(appointment.client_google_calendar_id == 'new_event_id')

    @pytest.mark.django_db
    @freeze_time('2018-11-24 10:00:00 EST')
    @mock.patch('appointment.models.build_oauth_http_object_from_tokens')
    @mock.patch('appointment.models.cancel_calendar_event')
    def test_cancel_client_google_calendar_event(self, cancel_mock, build_http_mock):
        salon: Salon = G(Salon, timezone=pytz.timezone('America/New_York'))
        stylist: Stylist = G(
            Stylist, salon=salon
        )
        client: Client = G(
            Client, google_access_token='access_token', google_refresh_token='refresh_token')
        appointment: Appointment = G(
            Appointment, status=AppointmentStatus.NEW, client=client,
            stylist=stylist, client_google_calendar_id='some_id'
        )
        appointment.cancel_client_google_calendar_event()
        build_http_mock.assert_not_called()
        cancel_mock.assert_not_called()
        appointment.status = AppointmentStatus.CANCELLED_BY_CLIENT
        appointment.save()

        appointment.cancel_client_google_calendar_event()
        build_http_mock.assert_called_once_with(
            access_token=client.google_access_token,
            refresh_token=client.google_refresh_token,
            model_object_to_update=client,
            access_token_field='google_access_token'
        )
        assert(cancel_mock.call_count == 1)
        assert (cancel_mock.call_args[1]['event_id'] == 'some_id')
