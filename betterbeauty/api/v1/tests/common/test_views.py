import mock
import pytest

from django.urls import reverse
from django_dynamic_fixture import G
from oauth2client.client import Error as oauth_error, OAuth2Credentials
from push_notifications.models import APNSDevice, GCMDevice
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.common.permissions import ClientOrStylistPermission
from api.v1.common.urls import urlpatterns
from api.v1.common.views import (
    TemporaryImageUploadView,
)
from client.models import Client
from core.models import User
from core.types import UserRole
from integrations.google.types import GoogleIntegrationErrors, GoogleIntegrationType
from integrations.push.constants import ErrorMessages
from salon.models import Stylist


class TestRegisterDeviceView(object):
    @pytest.mark.django_db
    def test_response_created(self, authorized_client_user, client):
        client_user, client_auth_token = authorized_client_user
        url = reverse('api:v1:common:register_device')
        data = {
            'device_registration_id': 'token token',
            'device_type': 'fcm',
            'user_role': 'stylist',
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)
        data = {
            'device_registration_id': 'token token',
            'device_type': 'fcm',
            'user_role': 'client',
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert(response.status_code == status.HTTP_201_CREATED)
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert (response.status_code == status.HTTP_200_OK)
        device = GCMDevice.objects.last()
        assert(device is not None)
        assert(device.user == client_user)
        assert(device.registration_id == 'tokentoken')

    @pytest.mark.django_db
    def test_duplicate_device(self, authorized_client_user, client):
        client_user, client_auth_token = authorized_client_user
        client_user.role = [UserRole.CLIENT, UserRole.STYLIST]
        client_user.save(update_fields=['role', ])
        url = reverse('api:v1:common:register_device')
        data = {
            'device_registration_id': 'token token',
            'device_type': 'apns',
            'user_role': 'client',
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert (response.status_code == status.HTTP_201_CREATED)
        data = {
            'device_registration_id': 'token token',
            'device_type': 'apns',
            'user_role': 'stylist',
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)
        assert(
            {'code': ErrorMessages.ERR_DUPLICATE_PUSH_TOKEN} in
            response.data['field_errors']['device_registration_id']
        )


class TestUnregisterDeviceView(object):
    @pytest.mark.django_db
    def test_device_not_found(self, authorized_client_user, client):
        client_user, client_auth_token = authorized_client_user
        client_user.role = [UserRole.CLIENT, ]
        foreign_user = G(User)
        client_user.save(update_fields=['role', ])
        device = G(
            APNSDevice, user=foreign_user, registration_id='tokentoken',
            application_id='ios_client')
        url = reverse('api:v1:common:unregister_device'
                      )
        data = {
            'device_registration_id': 'token token',
            'device_type': 'apns',
            'user_role': 'client',
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert(response.status_code == status.HTTP_404_NOT_FOUND)
        device.user = client_user
        device.save()
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert(response.status_code == status.HTTP_204_NO_CONTENT)


class TestIntegrationAddView(object):
    @pytest.mark.django_db
    def test_positive_path(
            self, client, mocker, authorized_client_user, authorized_stylist_user
    ):
        mocker.patch(
            'integrations.google.utils.get_oauth_credentials_from_server_code',
            lambda auth_code, scope: OAuth2Credentials(
                access_token='access_token', client_id='client_id',
                client_secret='client_secret', refresh_token='refresh_token',
                token_expiry=None, token_uri=None, user_agent=None
            )
        )
        url = reverse('api:v1:common:integration-add')
        client_user, client_auth_token = authorized_client_user
        stylist_user, stylist_auth_token = authorized_stylist_user
        # test client
        client_obj: Client = client_user.client
        assert(client_obj.google_integration_added_at is None)
        assert (client_obj.google_access_token is None)
        assert (client_obj.google_refresh_token is None)
        data = {
            'user_role': UserRole.CLIENT,
            'server_auth_code': 'some code',
            'integration_type': GoogleIntegrationType.GOOGLE_CALENDAR
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert(status.is_success(response.status_code))
        client_obj.refresh_from_db()
        assert (client_obj.google_integration_added_at is not None)
        assert (client_obj.google_access_token == 'access_token')
        assert (client_obj.google_refresh_token == 'refresh_token')
        # test stylist
        stylist: Stylist = stylist_user.stylist
        assert (stylist.google_integration_added_at is None)
        assert (stylist.google_access_token is None)
        assert (stylist.google_refresh_token is None)
        data = {
            'user_role': UserRole.STYLIST,
            'server_auth_code': 'some code',
            'integration_type': GoogleIntegrationType.GOOGLE_CALENDAR
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=stylist_auth_token
        )
        assert (status.is_success(response.status_code))
        stylist.refresh_from_db()
        assert (stylist.google_integration_added_at is not None)
        assert (stylist.google_access_token == 'access_token')
        assert (stylist.google_refresh_token == 'refresh_token')

    @pytest.mark.django_db
    @mock.patch('integrations.google.utils.get_oauth_credentials_from_server_code')
    def test_oauth_error(self, oauth_mock, client, authorized_client_user):
        oauth_mock.side_effect = oauth_error('Something went wrong')
        url = reverse('api:v1:common:integration-add')
        client_user, client_auth_token = authorized_client_user
        data = {
            'user_role': UserRole.CLIENT,
            'server_auth_code': 'some code',
            'integration_type': GoogleIntegrationType.GOOGLE_CALENDAR
        }
        response = client.post(
            url, data=data, HTTP_AUTHORIZATION=client_auth_token
        )
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)
        assert(
            {'code': GoogleIntegrationErrors.ERR_FAILURE_TO_SETUP_OAUTH} in
            response.data['non_field_errors']
        )


class TestCommonViewPermissions(object):
    def test_view_permissions(self):
        """Go over all configured urls an make sure they have necessary permissions"""
        for url_resolver in urlpatterns:
            view_class = url_resolver.callback.view_class
            if view_class is TemporaryImageUploadView:
                assert (
                    frozenset(view_class.permission_classes) == frozenset([
                        IsAuthenticated
                    ])
                )
            else:
                assert (
                    frozenset(view_class.permission_classes) == frozenset([
                        ClientOrStylistPermission, IsAuthenticated
                    ])
                )
