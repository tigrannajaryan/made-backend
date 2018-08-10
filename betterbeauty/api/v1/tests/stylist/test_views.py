import datetime

import mock
import pytest
import pytz

from django.urls import reverse

from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.common.permissions import StylistPermission, StylistRegisterUpdatePermission
from api.v1.stylist.serializers import AppointmentValidationMixin
from api.v1.stylist.urls import urlpatterns
from api.v1.stylist.views import ClientSearchView, StylistView
from appointment.constants import AppointmentStatus, ErrorMessages as appointment_errors
from appointment.models import Appointment
from client.models import Client, ClientOfStylist
from core.models import User
from core.types import UserRole
from salon.models import Salon, Stylist, StylistService


class TestStylistView(object):

    def _create_and_authorize_user(self, client):
        user = G(
            User, email='email@example.com', first_name='Jane', last_name='McBob',
            role=[UserRole.STYLIST]
        )
        user.set_password('password')
        user.save()
        auth_url = reverse('api:v1:auth:get_jwt_token')
        data = client.post(
            auth_url, data={
                'email': 'email@example.com', 'password': 'password', 'role': UserRole.STYLIST
            }
        ).data
        token = data['token']
        return user, token

    @pytest.mark.django_db
    def test_stylist_get_with_existing_stylist(self, client):
        user, token = self._create_and_authorize_user(client)
        stylist = G(Stylist, user=user)
        profile_url = reverse('api:v1:stylist:profile')
        auth_header = 'Token {0}'.format(token)
        response = client.get(profile_url, data={}, HTTP_AUTHORIZATION=auth_header)
        assert(response.status_code == status.HTTP_200_OK)
        data = response.data
        assert(data['first_name'] == 'Jane')
        assert(data['uuid'] == str(stylist.uuid))

    @pytest.mark.django_db
    def test_stylist_get_without_existing_stylist(self, client):
        user, token = self._create_and_authorize_user(client)
        profile_url = reverse('api:v1:stylist:profile')
        auth_header = 'Token {0}'.format(token)
        response = client.get(profile_url, data={}, HTTP_AUTHORIZATION=auth_header)
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert (not data['first_name'])
        assert ('id' not in data)


class TestClientSearchView(object):

    @pytest.mark.django_db
    def test_search_clients(self):
        stylist_1 = G(Stylist)
        # stray_client
        G(
            ClientOfStylist,
            first_name='Jenny',
            last_name='McDonald',
            phone='123456',
            stylist=stylist_1,
        )

        our_stylist = G(Stylist)
        # client that our stylist has appointments with
        our_client = G(
            ClientOfStylist,
            first_name='Fred',
            last_name='McBob',
            phone='123457',
            stylist=our_stylist,
        )

        G(Appointment, stylist=our_stylist, client=our_client)

        no_results = ClientSearchView()._search_clients(
            our_stylist.clients_of_stylist.all(), 'Jenny'
        )
        assert(no_results.count() == 0)
        results = ClientSearchView()._search_clients(
            our_stylist.clients_of_stylist.all(), 'Fred'
        )
        assert(results.count() == 1)
        assert(results.last() == our_client)

        results = ClientSearchView()._search_clients(
            our_stylist.clients_of_stylist.all(), 'Fred mc'
        )
        assert (results.count() == 1)
        assert (results.last() == our_client)

        results = ClientSearchView()._search_clients(
            our_stylist.clients_of_stylist.all(), 'mcbob fr'
        )
        assert (results.count() == 1)
        assert (results.last() == our_client)

        results = ClientSearchView()._search_clients(
            our_stylist.clients_of_stylist.all(), '12345'
        )
        assert (results.count() == 1)
        assert (results.last() == our_client)


class TestStylistServiceView(object):

    @pytest.mark.django_db
    def test_view_permissions(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        # verify that a stylist cannot delete others' service
        foreign_service = G(StylistService, duration=datetime.timedelta(0))
        url = reverse('api:v1:stylist:service', kwargs={'uuid': foreign_service.uuid})
        response = client.delete(
            url, HTTP_AUTHORIZATION=auth_token
        )
        assert(response.status_code == status.HTTP_404_NOT_FOUND)


class TestStylistAppointmentListCreateView(object):

    @pytest.mark.django_db
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_datetime_start_at', lambda s, a: a)
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_services', lambda s, a: a)
    def test_view_permissions(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        # verify that stylist cannot create appointment with a client
        # not in stylist's list, or with other stylists' services
        url = reverse('api:v1:stylist:appointments')
        foreign_client = G(Client)
        foreign_client_of_stylist = G(ClientOfStylist, client=foreign_client)
        data = {
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            'services': [],
            'client_uuid': foreign_client_of_stylist.uuid
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)
        assert(
            {'code': appointment_errors.ERR_CLIENT_DOES_NOT_EXIST} in
            response.data['field_errors']['client_uuid']
        )


class TestStylistAppointmentPreviewView(object):

    @pytest.mark.django_db
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_datetime_start_at', lambda s, a: a)
    @mock.patch.object(
        AppointmentValidationMixin, 'validate_services', lambda s, a: a)
    def test_view_permissions(self, client, authorized_stylist_user):
        # verify that stylist cannot preview appointment with others' client
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        stylist.salon = G(Salon, timezone=pytz.UTC)
        stylist.save()
        url = reverse('api:v1:stylist:appointment-preview')
        foreign_client = G(Client)
        foreign_client_of_stylist = G(ClientOfStylist, client=foreign_client)
        data = {
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            'services': [],
            'client_uuid': foreign_client_of_stylist.uuid
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert (
            {'code': appointment_errors.ERR_CLIENT_DOES_NOT_EXIST} in
            response.data['field_errors']['client_uuid']
        )
        foreign_appointment = G(
            Appointment,
            duration=datetime.timedelta(0),
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC)
        )
        data = {
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            'services': [],
            'appointment_uuid': foreign_appointment.uuid,
            'client_first_name': 'Fred',
            'client_last_name': 'McBob',
            'client_phone': '+16135501234'
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert (
            {'code': appointment_errors.ERR_APPOINTMENT_DOESNT_EXIST} in
            response.data['field_errors']['appointment_uuid']
        )


class TestStylistAppointmentRetrieveUpdateCancelView(object):

    @pytest.mark.django_db
    def test_view_permissions(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        our_appointment = G(
            Appointment,
            stylist=stylist,
            duration=datetime.timedelta(0),
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC)
        )
        foreign_appointment = G(
            Appointment,
            duration=datetime.timedelta(0),
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC)
        )
        # verify that stylist cannot view or update other stylists' appointments

        url = reverse(
            'api:v1:stylist:appointment', kwargs={'appointment_uuid': our_appointment.uuid}
        )
        data = {'status': AppointmentStatus.NO_SHOW}
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(status.is_success(response.status_code))
        url = reverse(
            'api:v1:stylist:appointment', kwargs={'appointment_uuid': foreign_appointment.uuid}
        )
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_404_NOT_FOUND)
        response = client.post(url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_404_NOT_FOUND)
        response = client.delete(url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_404_NOT_FOUND)


class TestStylistServicePricingView(object):

    @pytest.mark.django_db
    @mock.patch(
        'api.v1.stylist.serializers.generate_prices_for_stylist_service',
        lambda a, b, **kwargs: []
    )
    def test_view_permissions(self, client, authorized_stylist_user):
        # verify that stylist cannot check prices of other stylists' services
        # or get services for clients without a relation to them
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        url = reverse('api:v1:stylist:service-pricing')
        foreign_service = G(StylistService, duration=datetime.timedelta(0))
        foreign_client = G(ClientOfStylist)
        our_service = G(StylistService, duration=datetime.timedelta(0), stylist=stylist)
        our_client = G(ClientOfStylist, stylist=stylist)
        data = {
            'service_uuid': foreign_service.uuid
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)
        assert({'code': appointment_errors.ERR_SERVICE_DOES_NOT_EXIST} in
               response.data['field_errors']['service_uuid'])
        data = {
            'service_uuid': our_service.uuid,
            'client_uuid': our_client.uuid
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert (status.is_success(response.status_code))

        data = {
            'service_uuid': our_service.uuid,
            'client_uuid': foreign_client.uuid
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=auth_token
        )
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert ({'code': appointment_errors.ERR_CLIENT_DOES_NOT_EXIST} in
                response.data['field_errors']['client_uuid'])


class TestStylistViewPermissions(object):

    def test_view_permissions(self):
        """Go over all configured urls an make sure they have necessary permissions"""
        for url_resolver in urlpatterns:
            view_class = url_resolver.callback.view_class
            if view_class is StylistView:
                assert (
                    frozenset(view_class.permission_classes) == frozenset([
                        StylistRegisterUpdatePermission, IsAuthenticated
                    ])
                )
            else:
                assert (
                    frozenset(view_class.permission_classes) == frozenset([
                        StylistPermission, IsAuthenticated
                    ])
                )
