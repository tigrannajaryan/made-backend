import datetime

import mock
import pytest
import pytz

from django.urls import reverse
from django.utils import timezone

from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.common.permissions import StylistPermission, StylistRegisterUpdatePermission
from api.v1.stylist.serializers import AppointmentValidationMixin
from api.v1.stylist.urls import urlpatterns
from api.v1.stylist.views import StylistView
from appointment.constants import AppointmentStatus, ErrorMessages as appointment_errors
from appointment.models import Appointment, AppointmentService
from client.models import Client, PreferredStylist
from core.models import User
from core.types import UserRole
from salon.models import (
    Salon,
    Stylist,
    StylistService,
    StylistSpecialAvailableDate,
)
from salon.tests.test_models import stylist_appointments_data
from salon.utils import get_default_service_uuids


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
        data = {
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            'services': [],
            'client_uuid': foreign_client.uuid
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
        appointment = G(
            Appointment,
            duration=datetime.timedelta(0),
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            stylist=stylist
        )
        data = {
            'datetime_start_at': datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            'services': [],
            'client_uuid': foreign_client.uuid,
            'appointment_uuid': appointment.uuid,
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
        foreign_client = G(Client)
        our_service = G(StylistService, duration=datetime.timedelta(0), stylist=stylist)
        our_client = G(Client)
        G(PreferredStylist, client=our_client, stylist=stylist)
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


class TestClientListView(object):
    @pytest.mark.django_db
    def test_client_selection(self, client, authorized_stylist_user):
        """Verify that only stylist's client can be retrieved"""
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        client_data = G(Client)
        G(PreferredStylist, stylist=stylist, client=client_data)
        foreign_stylist = G(Stylist)
        foreign_client = G(Client)
        G(PreferredStylist, stylist=foreign_stylist, client=foreign_client)
        url = reverse('api:v1:stylist:my-clients')

        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))
        assert (len(response.data) == 1)
        assert (response.data['clients'][0]['uuid'] == str(client_data.uuid))


class TestClientView(object):
    @pytest.mark.django_db
    def test_client_selection(self, client, authorized_stylist_user):
        """Verify that only stylist's client can be retrieved"""
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        our_client = G(Client)
        G(PreferredStylist, client=our_client, stylist=stylist)
        foreign_client = G(Client)
        url = reverse('api:v1:stylist:client', kwargs={'client_uuid': foreign_client.uuid})

        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_404_NOT_FOUND)

        url = reverse('api:v1:stylist:client', kwargs={'client_uuid': our_client.uuid})

        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))


class TestClientPricingView(object):
    @pytest.mark.django_db
    def test_permissions(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        salon = G(Salon, timezone=pytz.UTC)
        stylist.salon = salon
        stylist.save(update_fields=['salon', ])
        our_service = G(StylistService, stylist=stylist)
        our_client = G(Client)
        G(PreferredStylist, stylist=stylist, client=our_client)
        foreign_client = G(Client)
        url = reverse('api:v1:stylist:client-pricing')
        data = {'client_uuid': foreign_client.uuid}
        response = client.post(url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)
        data = {'client_uuid': our_client.uuid}
        response = client.post(url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (status.is_success(response.status_code))
        assert(response.data['client_uuid'] == str(our_client.uuid))
        assert (response.data['service_uuids'] == [str(our_service.uuid), ])
        foreign_service = G(StylistService)
        data = {'client_uuid': our_client.uuid, 'service_uuids': [foreign_service. uuid]}
        response = client.post(url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        data = {'client_uuid': our_client.uuid, 'service_uuids': [our_service.uuid]}
        response = client.post(url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert(status.is_success(response.status_code))
        assert(response.data['client_uuid'] == str(our_client.uuid))
        assert(response.data['service_uuids'] == [str(our_service.uuid), ])

    @pytest.mark.django_db
    def test__get_default_service_uuids(self):
        stylist: Stylist = G(Stylist)
        client: Client = G(Client)
        G(PreferredStylist, stylist=stylist, client=client)

        assert(get_default_service_uuids(
            stylist=stylist, client=client) == [])
        service = G(StylistService, stylist=stylist)
        assert (get_default_service_uuids(
            stylist=stylist, client=client) == [service.uuid, ])
        popular_service = G(StylistService, stylist=stylist)
        appointment = G(
            Appointment, stylist=stylist,
            datetime_start_at=timezone.now() - datetime.timedelta(weeks=1),
            status=AppointmentStatus.CHECKED_OUT
        )
        G(AppointmentService, service_uuid=popular_service.uuid, appointment=appointment)
        assert (get_default_service_uuids(
            stylist=stylist, client=client) == [popular_service.uuid, ])
        last_appointment = G(
            Appointment, stylist=stylist, client=client,
            datetime_start_at=timezone.now() - datetime.timedelta(days=1),
            status=AppointmentStatus.CHECKED_OUT
        )
        G(AppointmentService, service_uuid=popular_service.uuid, appointment=last_appointment)
        G(AppointmentService, service_uuid=service.uuid, appointment=last_appointment)
        assert (sorted(get_default_service_uuids(
            stylist=stylist, client=client)) == sorted(
            [popular_service.uuid, service.uuid]
        ))


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


class TestAppointmentsOnADaySerializer(object):

    @pytest.mark.django_db
    def test_appointments_on_a_day(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        salon = G(Salon, timezone=pytz.utc)
        stylist.salon = salon
        stylist.save(update_fields=['salon', ])
        G(StylistService, stylist=stylist)
        stylist_appointments_data(stylist)
        url = reverse('api:v1:stylist:one-day-appointments')
        response_data = client.get(url, data={
            'date': '2018-05-14'
        }, HTTP_AUTHORIZATION=auth_token).data

        assert (len(response_data['appointments']) == 4)
        assert(response_data['service_time_gap_minutes'] == 30)
        assert(response_data['total_slot_count'] == 14)
        assert(response_data['work_start_at'] == datetime.time(hour=12))
        assert(response_data['work_end_at'] == datetime.time(hour=19))
        assert(response_data['is_day_available'])

    @pytest.mark.django_db
    def test_appointments_on_a_special_date(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist = user.stylist
        salon = G(Salon, timezone=pytz.utc)
        stylist.salon = salon
        stylist.save(update_fields=['salon', ])
        G(StylistService, stylist=stylist)
        G(StylistSpecialAvailableDate, stylist=stylist, date=datetime.date(2018, 5, 14))
        stylist_appointments_data(stylist)
        url = reverse('api:v1:stylist:one-day-appointments')
        response_data = client.get(url, data={
            'date': '2018-05-14'
        }, HTTP_AUTHORIZATION=auth_token).data

        assert (len(response_data['appointments']) == 4)
        assert (response_data['service_time_gap_minutes'] == 30)
        assert (response_data['total_slot_count'] == 0)
        assert (response_data['work_start_at'] is None)
        assert (response_data['work_end_at'] is None)
        assert (response_data['is_day_available'] is False)


class TestStylistSpecialAvailabilityDateView(object):
    @pytest.mark.django_db
    def test_create_update(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist: Stylist = user.stylist
        url = reverse(
            'api:v1:stylist:special-availability',
            args=[datetime.date(2018, 11, 29).isoformat()]
        )
        response = client.post(url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_201_CREATED)
        assert(stylist.special_available_dates.all().count() == 1)
        special_date = stylist.special_available_dates.last()
        assert(special_date.date == datetime.date(2018, 11, 29))
        assert(special_date.is_available is False)
        special_date.delete()
        response = client.post(url, data={'is_available': True}, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_201_CREATED)
        assert (stylist.special_available_dates.all().count() == 1)
        special_date = stylist.special_available_dates.last()
        assert (special_date.date == datetime.date(2018, 11, 29))
        assert (special_date.is_available is True)
        response = client.post(url, data={'is_available': False}, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_200_OK)
        assert (stylist.special_available_dates.all().count() == 1)
        special_date = stylist.special_available_dates.last()
        assert (special_date.date == datetime.date(2018, 11, 29))
        assert (special_date.is_available is False)

    @pytest.mark.django_db
    def test_retrieve(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist: Stylist = user.stylist
        G(
            StylistSpecialAvailableDate,
            stylist=stylist, date=datetime.date(2018, 11, 29), is_available=True
        )
        url = reverse(
            'api:v1:stylist:special-availability',
            args=[datetime.date(2018, 11, 28).isoformat()]
        )
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_404_NOT_FOUND)
        url = reverse(
            'api:v1:stylist:special-availability',
            args=[datetime.date(2018, 11, 29).isoformat()]
        )
        response = client.get(url, HTTP_AUTHORIZATION=auth_token)
        assert(response.status_code == status.HTTP_200_OK)
        assert(response.data == {'is_available': True})

    @pytest.mark.django_db
    def test_delete(self, client, authorized_stylist_user):
        user, auth_token = authorized_stylist_user
        stylist: Stylist = user.stylist
        url = reverse(
            'api:v1:stylist:special-availability',
            args=[datetime.date(2018, 11, 29).isoformat()]
        )
        response = client.delete(url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_404_NOT_FOUND)
        G(
            StylistSpecialAvailableDate,
            stylist=stylist, date=datetime.date(2018, 11, 29), is_available=True
        )
        response = client.delete(url, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_204_NO_CONTENT)
