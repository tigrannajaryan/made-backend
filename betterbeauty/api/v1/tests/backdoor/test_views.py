import datetime

import mock
import pytest

from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django_dynamic_fixture import G

from rest_framework import status

from api.common.permissions import BackdoorPermission
from api.v1.backdoor.urls import urlpatterns
from core.models import PhoneSMSCodes, User


CORRECT_API_KEY = 'SXcgbHVm6KUpEejdUKffcCd'
INCORRECT_API_KEY = 'DWWbFNZJ6Wghuh3Vf5LhhWh'
SHORT_API_KEY = 'N9UYBLHZ23dWBngw577'


class TestGetAuthCodeView(object):

    url = reverse('api:v1:backdoor:get-auth-code') + '?' + urlencode({
        'phone': '+15555550122'
    })

    @mock.patch.object(BackdoorPermission, '_get_backdoor_api_key', lambda a: CORRECT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_jwt_access(self, client, authorized_client_user, authorized_stylist_user):
        """Test that JWT-authorized user has not access to the view"""
        client_user, client_auth_token = authorized_client_user
        stylist_user, stylist_auth_token = authorized_stylist_user
        response = client.get(self.url, HTTP_AUTHORIZATION=client_auth_token)
        assert(response.status_code == status.HTTP_403_FORBIDDEN)
        response = client.get(self.url, HTTP_AUTHORIZATION=stylist_auth_token)
        assert (response.status_code == status.HTTP_403_FORBIDDEN)

    @mock.patch.object(BackdoorPermission, '_get_backdoor_api_key', lambda a: CORRECT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_api_key_permissions(self, client):
        """Test that wrong API key will not allow access"""
        G(PhoneSMSCodes, phone='+15555550122', redeemed_at=None)
        response = client.get(self.url)
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)
        response = client.get(
            self.url, HTTP_AUTHORIZATION='Secret {0}'.format(INCORRECT_API_KEY)
        )
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)
        response = client.get(
            self.url, HTTP_AUTHORIZATION='Secret {0}'.format(CORRECT_API_KEY)
        )
        assert(status.is_success(response.status_code))

    @mock.patch.object(BackdoorPermission, '_get_backdoor_api_key', lambda a: CORRECT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_non_fictional_number(self, client):
        """Test that a number not following pattern cannot be retrieved"""
        G(PhoneSMSCodes, phone='+15255550122', redeemed_at=None)
        url = reverse('api:v1:backdoor:get-auth-code') + '?' + urlencode({
            'phone': '+15255550122'
        })
        response = client.get(url, HTTP_AUTHORIZATION='Secret {0}'.format(CORRECT_API_KEY))
        assert (response.status_code == status.HTTP_404_NOT_FOUND)

    @mock.patch.object(BackdoorPermission, '_get_backdoor_api_key', lambda a: CORRECT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_old_user_account(self, client):
        """Test that a code created longer than 20 minutes ago cannot be retrieved"""
        G(
            PhoneSMSCodes, phone='+15555550122', redeemed_at=None,
        )
        old_user = G(
            User, phone='+15555550122', date_joined=timezone.now() - datetime.timedelta(minutes=21)
        )
        response = client.get(self.url, HTTP_AUTHORIZATION='Secret {0}'.format(CORRECT_API_KEY))
        assert (response.status_code == status.HTTP_404_NOT_FOUND)
        old_user.date_joined = timezone.now() - datetime.timedelta(minutes=19)
        old_user.save(update_fields=['date_joined', ])
        response = client.get(self.url, HTTP_AUTHORIZATION='Secret {0}'.format(CORRECT_API_KEY))
        assert (status.is_success(response.status_code))

    @mock.patch.object(BackdoorPermission, '_get_backdoor_api_key', lambda a: CORRECT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='production')
    def test_non_staging(self, client):
        G(
            PhoneSMSCodes, phone='+15555550122', redeemed_at=None
        )
        response = client.get(self.url, HTTP_AUTHORIZATION='Secret {0}'.format(CORRECT_API_KEY))
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)

    @mock.patch.object(BackdoorPermission, '_get_backdoor_api_key', lambda a: CORRECT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_positive_path(self, client):
        sms_code = G(
            PhoneSMSCodes, phone='+15555550122', redeemed_at=None
        )
        response = client.get(self.url, HTTP_AUTHORIZATION='Secret {0}'.format(CORRECT_API_KEY))
        assert (response.status_code == status.HTTP_200_OK)
        assert(response.data['code'] == sms_code.code)

    @mock.patch.object(BackdoorPermission, '_get_backdoor_api_key', lambda a: CORRECT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_no_or_empty_key(self, client):
        G(
            PhoneSMSCodes, phone='+15555550122', redeemed_at=None
        )
        response = client.get(self.url, HTTP_AUTHORIZATION='Secret ')
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)
        response = client.get(self.url)
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)

    @mock.patch('os.environ.get', lambda a, _: SHORT_API_KEY)
    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_short_key_restriction(self, client):
        G(
            PhoneSMSCodes, phone='+15555550122', redeemed_at=None
        )
        response = client.get(self.url, HTTP_AUTHORIZATION='Secret {0}'.format(SHORT_API_KEY))
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)

    @pytest.mark.django_db
    @override_settings(LEVEL='staging')
    def test_unset_api_key(self, client):
        G(
            PhoneSMSCodes, phone='+15555550122', redeemed_at=None
        )
        response = client.get(self.url, HTTP_AUTHORIZATION='')
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)
        response = client.get(self.url, HTTP_AUTHORIZATION='Secret ')
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)
        response = client.get(self.url)
        assert (response.status_code == status.HTTP_401_UNAUTHORIZED)


class TestBackdoorViewPermissions(object):

    def test_view_permissions(self):
        """Go over all configured urls an make sure they have necessary permissions"""
        for url_resolver in urlpatterns:
            view_class = url_resolver.callback.view_class
            assert (
                frozenset(view_class.permission_classes) == frozenset([
                    BackdoorPermission
                ])
            )
