import pytest

from django.urls import reverse
from django_dynamic_fixture import G
from push_notifications.models import APNSDevice, GCMDevice
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.common.permissions import ClientOrStylistPermission
from api.v1.common.urls import urlpatterns
from api.v1.common.views import TemporaryImageUploadView
from core.models import User
from core.types import UserRole
from integrations.push.constants import ErrorMessages


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
