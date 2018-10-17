import datetime
import json
import uuid
from typing import Dict

import mock
import pytest
import pytz

from dateutil import parser
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils import timezone
from django_dynamic_fixture import G
from freezegun import freeze_time
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.common.constants import HIGH_LEVEL_API_ERROR_CODES as common_errors
from api.common.permissions import ClientPermission
from api.v1.client.constants import ErrorMessages as client_errors, NEW_YORK_LOCATION
from api.v1.client.serializers import AppointmentValidationMixin
from api.v1.client.urls import urlpatterns
from api.v1.client.views import HistoryView, HomeView, SearchStylistView
from appointment.constants import (
    AppointmentStatus,
    ErrorMessages as appointment_errors,
)
from appointment.models import Appointment
from client.models import Client, PreferredStylist
from client.types import ClientPrivacy
from salon.models import Salon, Stylist, StylistService
from salon.tests.test_models import stylist_appointments_data


class TestClientProfileView:

    @pytest.mark.django_db
    def test_submit_profile(self, client, authorized_client_user):
        user, auth_token = authorized_client_user
        data = {
            'phone': user.phone,
            'first_name': 'Tom',
            'last_name': 'Cruise',
            "email": 'test@example.com'
        }
        profile_url = reverse('api:v1:client:client-profile')
        response = client.post(profile_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert (data['first_name'] == 'Tom')
        assert (data['last_name'] == 'Cruise')

    @pytest.mark.django_db
    def test_update_profile(self, client, authorized_client_user):
        user, auth_token = authorized_client_user
        data = {
            'first_name': 'Tom',
            'last_name': 'Cruise',
            'email': 'test@example.com'
        }
        profile_url = reverse('api:v1:client:client-profile')

        response = client.post(profile_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert (data['first_name'] == 'Tom')
        assert (data['last_name'] == 'Cruise')
        updated_data = {
            'first_name': 'Tommy'
        }

        response = client.patch(profile_url, data=json.dumps(updated_data),
                                HTTP_AUTHORIZATION=auth_token,
                                content_type='application/json')
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert (data['first_name'] == 'Tommy')
        assert (data['last_name'] == 'Cruise')

    @pytest.mark.django_db
    def test_view_permissions(
            self, client, authorized_stylist_user, authorized_client_user
    ):
        user, token = authorized_stylist_user
        data = {
            'first_name': 'Tom',
            'last_name': 'Cruise',
            'email': 'test@example.com'
        }
        profile_url = reverse('api:v1:client:client-profile')

        response = client.post(profile_url, data=data, HTTP_AUTHORIZATION=token)
        assert(response.status_code == status.HTTP_403_FORBIDDEN)

        user, token = authorized_client_user
        data = {
            'first_name': 'Tom',
            'last_name': 'Cruise',
            'email': 'test@example.com'
        }
        profile_url = reverse('api:v1:client:client-profile')

        response = client.post(profile_url, data=data, HTTP_AUTHORIZATION=token)
        assert(status.is_success(response.status_code))


class TestPreferredStylistListCreateView(object):

    @pytest.mark.django_db
    def test_add_preferred_stylists(
            self, client, stylist_data: Stylist, authorized_client_user
    ):
        user, auth_token = authorized_client_user
        data = {
            'stylist_uuid': stylist_data.uuid
        }
        preferred_stylist_url = reverse('api:v1:client:preferred-stylist')
        response = client.post(preferred_stylist_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_201_CREATED)
        response_data = response.data
        assert (response_data['preference_uuid'] is not None)

        response = client.post(preferred_stylist_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)

        response = client.get(preferred_stylist_url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert (len(data['stylists']) == 1)
        assert (data['stylists'][0]['uuid'] == str(stylist_data.uuid))

    @pytest.mark.django_db
    def test_list_preferred_stylists(
            self, client, authorized_client_user
    ):
        user, auth_token = authorized_client_user
        client_obj = user.client
        other_client = G(Client)
        our_stylist = G(Stylist)
        foreign_stylist = G(Stylist)
        G(PreferredStylist, client=client_obj, stylist=our_stylist)
        G(PreferredStylist, client=other_client, stylist=foreign_stylist)
        preferred_stylists_url = reverse('api:v1:client:preferred-stylist')
        response = client.get(preferred_stylists_url, HTTP_AUTHORIZATION=auth_token)
        assert(status.is_success(response.status_code))
        assert (
            frozenset([str(c['uuid']) for c in response.data['stylists']]) ==
            frozenset([str(our_stylist.uuid), ])
        )

    @pytest.mark.django_db
    def test_view_permissions(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        preferred_stylists_url = reverse('api:v1:client:preferred-stylist')
        response = client.get(preferred_stylists_url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_403_FORBIDDEN)
        response = client.post(preferred_stylists_url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_403_FORBIDDEN)


class TestPreferredStylistDeleteView(object):

    @pytest.mark.django_db
    def test_delete_preferred_stylist(
            self, client, stylist_data: Stylist, authorized_client_user
    ):
        user, auth_token = authorized_client_user
        data = {
            'stylist_uuid': stylist_data.uuid
        }
        preferred_stylist_url = reverse('api:v1:client:preferred-stylist')
        response = client.post(preferred_stylist_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_201_CREATED)
        response_data = response.data
        assert (response_data['preference_uuid'] is not None)

        delete_preferred_stylist_url = reverse('api:v1:client:preferred-stylist-delete', kwargs={
            'uuid': response_data['preference_uuid']
        })

        response = client.delete(delete_preferred_stylist_url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_204_NO_CONTENT)

        response = client.get(preferred_stylist_url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert (len(data['stylists']) == 0)

    @pytest.mark.django_db
    def test_view_permissions(self, client, authorized_client_user, authorized_stylist_user):
        user, auth_token = authorized_client_user
        client_obj = user.client
        other_client = G(Client)
        our_stylist = G(Stylist)
        foreign_stylist = G(Stylist)
        our_preference = G(PreferredStylist, client=client_obj, stylist=our_stylist)
        foreign_preference = G(PreferredStylist, client=other_client, stylist=foreign_stylist)

        # try deleting others' preferred stylist
        delete_preferred_stylist_url = reverse('api:v1:client:preferred-stylist-delete', kwargs={
            'uuid': foreign_preference.uuid
        })
        response = client.delete(delete_preferred_stylist_url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_404_NOT_FOUND)

        delete_preferred_stylist_url = reverse('api:v1:client:preferred-stylist-delete', kwargs={
            'uuid': our_preference.uuid
        })
        # try without client permission
        user, auth_token = authorized_stylist_user
        response = client.delete(delete_preferred_stylist_url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_403_FORBIDDEN)

        # ensure positive path
        user, auth_token = authorized_client_user
        response = client.delete(delete_preferred_stylist_url, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))


class TestSearchStylistView(object):
    @pytest.mark.django_db
    def test_search_stylists(self, client, stylist_data: Stylist):
        location = stylist_data.salon.location
        G(Salon, location=location)
        stylist_data_2 = G(Stylist)

        accuracy = 50000
        results = SearchStylistView._search_stylists(
            '', '', location=location, accuracy=accuracy)
        assert (len(results) == 1)

        results = SearchStylistView._search_stylists(
            'Fred', 'los altos', location=location, accuracy=accuracy)
        assert (len(results) == 1)
        assert (results[0] == stylist_data)
        results = SearchStylistView._search_stylists(
            'mcbob fr', 'rilma', location=location, accuracy=accuracy)
        assert (len(results) == 1)
        assert (results[0] == stylist_data)
        results = SearchStylistView._search_stylists(
            'mcbob fr', 'junk-address', location=location, accuracy=accuracy)
        assert (len(results) == 0)
        salon = stylist_data_2.salon
        salon.location = location
        salon.save()
        results = SearchStylistView._search_stylists(
            stylist_data_2.get_full_name(), '', location=location, accuracy=accuracy)
        assert (len(results) == 1)
        assert (results[0] == stylist_data_2)

        results = SearchStylistView._search_stylists(
            'some-junk-text', '', location=location, accuracy=accuracy)
        assert (len(results) == 0)

    @pytest.mark.django_db
    def test_search_stylists_when_no_results(self, stylist_data: Stylist):
        salon_2 = G(Salon, location=NEW_YORK_LOCATION)
        stylist_data_2 = G(Stylist, salon=salon_2)
        location = Point(77.303474, 11.1503445)
        accuracy = 50000

        results = SearchStylistView._search_stylists(
            '', '', location=location, accuracy=accuracy)
        assert (len(results) == 1)
        assert results[0] == stylist_data_2

    @pytest.mark.django_db
    def test_view_permissions(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist_search_url = reverse('api:v1:client:search-stylist')
        response = client.post(
            stylist_search_url,
            data={}, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_403_FORBIDDEN)


class TestStylistServicesView(object):

    @pytest.mark.django_db
    def test_view_permissions(
            self, client, authorized_stylist_user, authorized_client_user
    ):
        stylist = G(Stylist)
        user, auth_token = authorized_client_user
        client_obj = user.client
        preference = G(PreferredStylist, client=client_obj, stylist=stylist)

        stylist_service_url = reverse('api:v1:client:stylist-services', kwargs={
            'uuid': stylist.uuid
        })
        response = client.get(
            stylist_service_url,
            data={}, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))

        preference.delete()

        response = client.get(
            stylist_service_url,
            data={}, HTTP_AUTHORIZATION=auth_token)
        assert (not status.is_success(response.status_code))


class TestStylistServicePriceView(object):

    @pytest.mark.django_db
    def test_view_permissions(self, client, authorized_stylist_user, authorized_client_user):
        our_stylist = G(Stylist)
        foreign_stylist = G(Stylist)
        user, auth_token = authorized_client_user
        client_obj = user.client
        G(PreferredStylist, client=client_obj, stylist=our_stylist)
        our_service = G(StylistService, stylist=our_stylist, duration=datetime.timedelta(0))
        foreign_service = G(
            StylistService, stylist=foreign_stylist, duration=datetime.timedelta(0)
        )
        client_service_pricing_url = reverse('api:v1:client:services-pricing')
        response = client.post(
            client_service_pricing_url,
            data={
                'service_uuids': [our_service.uuid]
            }, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))

        response = client.post(
            client_service_pricing_url,
            data={
                'service_uuids': [our_service.uuid,
                                  foreign_service.uuid]
            }, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert (
            {'code': appointment_errors.ERR_SERVICE_DOES_NOT_EXIST} in
            response.data['field_errors']['service_uuids']
        )

        user, auth_token = authorized_stylist_user
        response = client.post(
            client_service_pricing_url,
            data={
                'service_uuid': our_service.uuid
            }, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_403_FORBIDDEN)


class TestAppointmentListCreateAPIView(object):

    @pytest.mark.django_db
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_datetime_start_at', lambda s, a: a)
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_services', lambda s, a: a)
    def test_view_permissions(self, client, authorized_client_user, authorized_stylist_user):
        user, auth_token = authorized_client_user
        client_obj = user.client
        appointments_url = reverse('api:v1:client:appointments')
        stylist = G(Stylist)
        # test create with non-preferred user
        data = {
            'stylist_uuid': stylist.uuid,
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0, 0),
            'services': []
        }
        response = client.post(
            appointments_url,
            data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)

        assert(
            {'code': appointment_errors.ERR_NOT_A_PREFERRED_STYLIST} in
            response.data['field_errors']['stylist_uuid']
        )
        user, auth_token = authorized_stylist_user
        response = client.post(
            appointments_url,
            data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert (response.status_code == status.HTTP_403_FORBIDDEN)

        # test list others' appointments
        user, auth_token = authorized_client_user

        foreign_client = G(Client)
        our_appointment = G(
            Appointment,
            client=client_obj,
            created_by=user
        )
        G(Appointment, client=foreign_client, created_by=user)
        response = client.get(
            appointments_url, HTTP_AUTHORIZATION=auth_token
        )
        assert(frozenset([a['uuid'] for a in response.data]) == frozenset([
            str(our_appointment.uuid)
        ]))
        user, auth_token = authorized_stylist_user
        response = client.get(
            appointments_url, HTTP_AUTHORIZATION=auth_token
        )
        assert (response.status_code == status.HTTP_403_FORBIDDEN)


class TestAppointmentRetriveUpdateView(object):

    @pytest.mark.django_db
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_datetime_start_at', lambda s, a: a)
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_services', lambda s, a: a)
    def test_view_permissions(
            self, client, authorized_client_user, authorized_stylist_user
    ):
        user, auth_token = authorized_client_user
        client_obj = user.client
        stylist = G(Stylist)
        foreign_client = G(Client)
        our_appointment = G(
            Appointment,
            client=client_obj,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            stylist=stylist
        )
        foreign_appointment = G(
            Appointment,
            client=foreign_client,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            stylist=stylist
        )
        # test retrieve
        appointment_url = reverse(
            'api:v1:client:appointment', kwargs={'uuid': foreign_appointment.uuid}
        )
        response = client.get(appointment_url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_404_NOT_FOUND)
        appointment_url = reverse(
            'api:v1:client:appointment', kwargs={'uuid': our_appointment.uuid}
        )
        response = client.get(appointment_url, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))

        # test update
        data = {'status': AppointmentStatus.CANCELLED_BY_CLIENT}

        appointment_url = reverse(
            'api:v1:client:appointment', kwargs={'uuid': foreign_appointment.uuid}
        )
        response = client.post(
            appointment_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_404_NOT_FOUND)
        appointment_url = reverse(
            'api:v1:client:appointment', kwargs={'uuid': our_appointment.uuid}
        )
        response = client.post(
            appointment_url, data=data, HTTP_AUTHORIZATION=auth_token,
        )
        assert (status.is_success(response.status_code))


class TestAvailableTimeSlotView(object):

    @pytest.mark.django_db
    @freeze_time('2018-05-14 13:30:00 UTC')
    def test_view_permissions(
            self, client, authorized_client_user, stylist_data
    ):
        user, auth_token = authorized_client_user
        client_obj = user.client
        other_client = G(Client)
        our_stylist = stylist_data
        salon = G(Salon, timezone=pytz.utc)
        foreign_stylist = G(Stylist, salon=salon)
        G(PreferredStylist, client=client_obj, stylist=our_stylist)
        G(PreferredStylist, client=other_client, stylist=foreign_stylist)
        date = datetime.datetime.now().date()
        availability_url = reverse(
            'api:v1:client:available-times'
        )
        stylist_appointments_data(our_stylist)
        our_stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        response = client.post(availability_url, HTTP_AUTHORIZATION=auth_token, data={
            "date": "2018-05-14",
            "stylist_uuid": our_stylist.uuid})
        assert (status.is_success(response.status_code))

        start_times = [slot['start'] for slot in response.data['time_slots']]
        # assert all the returned slots are future slots
        assert all(parser.parse(date) > timezone.now() for date in start_times)

        stylist_appointments_data(foreign_stylist)
        foreign_stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        response = client.post(availability_url, HTTP_AUTHORIZATION=auth_token, data={
            "date": "2018-05-14",
            "stylist_uuid": foreign_stylist.uuid})
        assert (response.status_code == status.HTTP_404_NOT_FOUND)

    @pytest.mark.django_db
    @freeze_time('2018-05-14 22:30:00 UTC')
    def test_after_stylist_eod(
            self, client, authorized_client_user, stylist_data
    ):
        user, auth_token = authorized_client_user
        client_obj = user.client
        other_client = G(Client)
        our_stylist = stylist_data
        salon = G(Salon, timezone=pytz.utc)
        foreign_stylist = G(Stylist, salon=salon)
        G(PreferredStylist, client=client_obj, stylist=our_stylist)
        G(PreferredStylist, client=other_client, stylist=foreign_stylist)
        availability_url = reverse(
            'api:v1:client:available-times'
        )
        stylist_appointments_data(our_stylist)
        date = datetime.date(2018, 5, 13)
        our_stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        response = client.post(availability_url, HTTP_AUTHORIZATION=auth_token, data={
            "date": "2018-05-13",
            "stylist_uuid": our_stylist.uuid})
        # Return empty for past dates
        assert len(response.data['time_slots']) == 0

        date = datetime.date(2018, 5, 14)
        our_stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        response = client.post(availability_url, HTTP_AUTHORIZATION=auth_token, data={
            "date": "2018-05-14",
            "stylist_uuid": our_stylist.uuid})
        # Return empty if time is past stylist end of day
        assert len(response.data['time_slots']) == 0

        date = datetime.date(2018, 5, 15)
        our_stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        response = client.post(availability_url, HTTP_AUTHORIZATION=auth_token, data={
            "date": "2018-05-15",
            "stylist_uuid": our_stylist.uuid})
        # Return actual slots for tomorrow's date
        assert len(response.data['time_slots']) > 0

        date = datetime.date(2018, 5, 16)
        our_stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="11:01", is_available=True)
        response = client.post(availability_url, HTTP_AUTHORIZATION=auth_token, data={
            "date": "2018-05-16",
            "stylist_uuid": our_stylist.uuid})
        assert len(response.data['time_slots']) == 5

        service = our_stylist.services.first()
        data = {
            'stylist_uuid': str(our_stylist.uuid),
            'datetime_start_at': '2018-05-16T11:00:00+00:00',
            'services': [
                {'service_uuid': str(service.uuid)}
            ]
        }
        appointments_url = reverse(
            'api:v1:client:appointments'
        )
        response = client.post(appointments_url, HTTP_AUTHORIZATION=auth_token,
                               data=json.dumps(data), content_type='application/json')
        assert (status.is_success(response.status_code))


class TestClientViewPermissions(object):

    def test_view_permissions(self):
        """Go over all configured urls an make sure they have necessary permissions"""
        for url_resolver in urlpatterns:
            view_class = url_resolver.callback.view_class
            assert (
                frozenset(view_class.permission_classes) == frozenset([
                    ClientPermission, IsAuthenticated
                ])
            )


class TestHomeAPIView(object):

    @freeze_time('2018-05-14 14:10:00 UTC')
    def test_get_upcoming_appointments(self, stylist_data, client_data):
        client: Client = client_data
        G(PreferredStylist, client=client, stylist=stylist_data)
        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)

        appointments['past_appointment'].set_status(
            AppointmentStatus.CHECKED_OUT, updated_by=stylist_data.user)
        appointments['future_appointment'].set_status(
            AppointmentStatus.CHECKED_OUT, updated_by=stylist_data.user)

        for a in appointments.values():
            a.client = client
            a.save(update_fields=['client', ])
        upcoming_appointments = HomeView.get_upcoming_appointments(client)

        assert (upcoming_appointments.count() == 4)

    @freeze_time('2018-05-14 13:00:00 UTC')
    def test_get_last_visit(self, stylist_data, client_data):
        client: Client = client_data
        G(PreferredStylist, client=client, stylist=stylist_data)

        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)
        appointments['last_week_appointment'].set_status(
            AppointmentStatus.CHECKED_OUT, updated_by=stylist_data.user)

        for a in appointments.values():
            a.client = client
            a.save(update_fields=['client', ])

        last_appointment = HomeView.get_last_visited_object(client)

        assert (last_appointment == appointments['last_week_appointment'])


class TestHistoryAPIView(object):

    @freeze_time('2018-05-14 14:00:00 UTC')
    def test_historical_appointments(self, stylist_data, client_data):
        client: Client = client_data
        G(PreferredStylist, client=client, stylist=stylist_data)
        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)
        appointments['current_appointment'].set_status(status=AppointmentStatus.CHECKED_OUT,
                                                       updated_by=client.user)
        for a in appointments.values():
            a.client = client
            a.save(update_fields=['client', ])
        past_appointments = HistoryView.get_historical_appointments(client)
        assert (past_appointments.count() == 2)


class TestStylistFollowersView(object):
    @pytest.mark.django_db
    def test_stylist_validation(self, client, authorized_client_user):
        """Verify that non-preferred or missing stylist raise 404"""
        user, auth_token = authorized_client_user
        client_obj: Client = user.client
        url = reverse('api:v1:client:stylist-followers', kwargs={'stylist_uuid': uuid.uuid4()})
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_404_NOT_FOUND)
        assert(
            appointment_errors.ERR_STYLIST_DOES_NOT_EXIST in
            response.data['non_field_errors']
        )
        assert(response.data['code'] == common_errors[404])

        foreign_stylist = G(Stylist)
        url = reverse(
            'api:v1:client:stylist-followers', kwargs={'stylist_uuid': foreign_stylist.uuid}
        )
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_404_NOT_FOUND)
        assert(
            appointment_errors.ERR_STYLIST_DOES_NOT_EXIST in
            response.data['non_field_errors']
        )
        assert(response.data['code'] == common_errors[404])

        G(PreferredStylist, stylist=foreign_stylist, client=client_obj)
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(status.is_success(response.status_code))

    @pytest.mark.django_db
    def test_privacy_setting(self, client, authorized_client_user):
        """Verify that if current client has private setting, 400 is returned"""
        user, auth_token = authorized_client_user
        client_obj: Client = user.client
        client_obj.privacy = ClientPrivacy.PRIVATE
        client_obj.save(update_fields=['privacy', ])
        stylist: Stylist = G(Stylist)
        G(PreferredStylist, stylist=stylist, client=client_obj)
        url = reverse('api:v1:client:stylist-followers', kwargs={'stylist_uuid': stylist.uuid})
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert (response.data['code'] == common_errors[400])
        assert (
            client_errors.ERR_PRIVACY_SETTING_PRIVATE in
            response.data['non_field_errors']
        )

    @pytest.mark.django_db
    def test_output(self, client, authorized_client_user):
        user, auth_token = authorized_client_user
        client_obj: Client = user.client
        stylist: Stylist = G(Stylist)
        G(PreferredStylist, stylist=stylist, client=client_obj)

        client_with_privacy = G(Client, privacy=ClientPrivacy.PRIVATE)
        G(PreferredStylist, stylist=stylist, client=client_with_privacy)
        G(
            Appointment, status=AppointmentStatus.CHECKED_OUT,
            client=client_with_privacy, stylist=stylist
        )
        client_with_cancelled_appointment = G(Client)
        G(PreferredStylist, stylist=stylist, client=client_with_cancelled_appointment)
        G(
            Appointment, status=AppointmentStatus.CANCELLED_BY_CLIENT,
            client=client_with_cancelled_appointment, stylist=stylist
        )
        client_with_successful_appointment = G(Client)
        G(PreferredStylist, stylist=stylist, client=client_with_successful_appointment)
        G(
            Appointment, status=AppointmentStatus.CHECKED_OUT,
            client=client_with_successful_appointment, stylist=stylist
        )
        client_with_new_appointment = G(Client)
        G(PreferredStylist, stylist=stylist, client=client_with_new_appointment)
        G(
            Appointment, status=AppointmentStatus.NEW,
            client=client_with_new_appointment, stylist=stylist
        )
        client_without_appointments = G(Client)
        G(PreferredStylist, stylist=stylist, client=client_without_appointments)

        url = reverse('api:v1:client:stylist-followers', kwargs={'stylist_uuid': stylist.uuid})
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(status.is_success(response.status_code))
        assert(frozenset([r['uuid'] for r in response.data['followers']]) == frozenset([
            str(client_with_successful_appointment.uuid),
            str(client_with_new_appointment.uuid),
            str(client_with_cancelled_appointment.uuid),
            str(client_without_appointments.uuid)
        ]))

        appt_count = {u['uuid']: u['booking_count'] for u in response.data['followers']}
        assert(appt_count[str(client_with_successful_appointment.uuid)] == 1)
        assert(appt_count[str(client_with_new_appointment.uuid)] == 1)
        assert(appt_count[str(client_with_cancelled_appointment.uuid)] == 0)
        assert(appt_count[str(client_without_appointments.uuid)] == 0)
