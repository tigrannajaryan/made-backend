import datetime
import json
from typing import Dict

import mock
import pytest
import pytz

from django.urls import reverse
from django_dynamic_fixture import G
from freezegun import freeze_time
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.common.permissions import ClientPermission
from api.v1.client.serializers import AppointmentValidationMixin
from api.v1.client.urls import urlpatterns
from api.v1.client.views import HistoryView, HomeView, SearchStylistView
from appointment.constants import (
    AppointmentStatus,
    ErrorMessages as appointment_errors,
)
from appointment.models import Appointment
from client.models import Client, PreferredStylist
from salon.models import ClientOfStylist, Salon, Stylist, StylistService
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

        stylist_data_2 = G(Stylist)
        location = stylist_data.salon.location
        accuracy = 50000
        results = SearchStylistView._search_stylists(
            '', location=location, accuracy=accuracy)
        assert (results.count() == 1)

        results = SearchStylistView._search_stylists(
            'Fred', location=location, accuracy=accuracy)
        assert (results.count() == 1)
        assert (results.last() == stylist_data)
        results = SearchStylistView._search_stylists(
            'mcbob fr', location=location, accuracy=accuracy)
        assert (results.count() == 1)
        assert (results.last() == stylist_data)
        salon = stylist_data_2.salon
        salon.location = location
        salon.save()
        results = SearchStylistView._search_stylists(
            stylist_data_2.get_full_name(), location=location, accuracy=accuracy)
        assert (results.count() == 1)
        assert (results.last() == stylist_data_2)

        results = SearchStylistView._search_stylists(
            'some-junk-text', location=location, accuracy=accuracy)
        assert (results.count() == 0)

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

        relation = G(
            ClientOfStylist,
            stylist=stylist,
            client=client_obj
        )

        response = client.get(
            stylist_service_url,
            data={}, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))

        relation.delete()

        stylist_service_url = reverse('api:v1:client:stylist-services', kwargs={
            'uuid': stylist.uuid
        })
        response = client.get(
            stylist_service_url,
            data={}, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_404_NOT_FOUND)

        user, auth_token = authorized_stylist_user
        response = client.get(
            stylist_service_url,
            data={}, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_403_FORBIDDEN)


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
        client_of_stylist = G(ClientOfStylist, client=client_obj)
        foreign_client_of_stylist = G(ClientOfStylist)
        our_appointment = G(
            Appointment,
            client=client_of_stylist,
            created_by=user
        )
        G(Appointment, client=foreign_client_of_stylist, created_by=user)
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
        our_client_of_stylist = G(ClientOfStylist, client=client_obj, stylist=stylist)
        foreign_client_of_stylist = G(ClientOfStylist, stylist=stylist)
        our_appointment = G(
            Appointment,
            client=our_client_of_stylist,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            stylist=stylist
        )
        foreign_appointment = G(
            Appointment,
            client=foreign_client_of_stylist,
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

        stylist_appointments_data(foreign_stylist)
        foreign_stylist.available_days.filter(weekday=date.isoweekday()).update(
            work_start_at="09:00", work_end_at="18:00", is_available=True)
        response = client.post(availability_url, HTTP_AUTHORIZATION=auth_token, data={
            "date": "2018-05-14",
            "stylist_uuid": foreign_stylist.uuid})
        assert (response.status_code == status.HTTP_404_NOT_FOUND)


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
        client_of_stylist = G(
            ClientOfStylist,
            client=client,
            stylist=stylist_data
        )
        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)

        for a in appointments.values():
            a.client = client_of_stylist
            a.save(update_fields=['client', ])
        upcoming_appointments = HomeView.get_upcoming_appointments(client)

        assert (upcoming_appointments.count() == 4)

    @freeze_time('2018-05-14 13:00:00 UTC')
    def test_get_last_visit(self, stylist_data, client_data):
        client: Client = client_data
        client_of_stylist = G(
            ClientOfStylist,
            client=client,
            stylist=stylist_data
        )
        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)

        for a in appointments.values():
            a.client = client_of_stylist
            a.save(update_fields=['client', ])
        last_appointment = HomeView.get_last_visited_object(client)
        assert (last_appointment == appointments['past_appointment'])


class TestHistoryAPIView(object):

    @freeze_time('2018-05-14 14:00:00 UTC')
    def test_historical_appointments(self, stylist_data, client_data):
        client: Client = client_data
        client_of_stylist = G(
            ClientOfStylist,
            client=client,
            stylist=stylist_data
        )
        appointments: Dict[str, Appointment] = stylist_appointments_data(stylist_data)

        for a in appointments.values():
            a.client = client_of_stylist
            a.save(update_fields=['client', ])
        past_appointments = HistoryView.get_historical_appointments(client)
        assert (past_appointments.count() == 3)
