import json

import pytest
from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status

from api.v1.auth.utils import create_client_profile_from_phone
from api.v1.client.views import SearchStylistView
from client.models import PhoneSMSCodes
from salon.models import Stylist


def _create_and_authorize_user(client):
    user = create_client_profile_from_phone('+19876543210')
    code = PhoneSMSCodes.create_or_update_phone_sms_code('+19876543210')
    auth_url = reverse('api:v1:auth:verify-code')
    data = client.post(
        auth_url, data={
            'phone': '+19876543210',
            'code': code.code,
        }
    ).data
    token = data['token']
    auth_token = 'Token {0}'.format(token)
    return user, auth_token


class TestClientProfile:

    @pytest.mark.django_db
    def test_submit_profile(self, client):
        user, auth_token = _create_and_authorize_user(client)
        data = {
            'phone': user.phone,
            'first_name': "Tom",
            'last_name': "Cruise",
            "email": 'test@example.com'
        }
        profile_url = reverse('api:v1:client:client-profile')
        response = client.post(profile_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_201_CREATED)
        data = response.data
        assert (data['first_name'] == 'Tom')
        assert (data['last_name'] == 'Cruise')

    @pytest.mark.django_db
    def test_update_profile(self, client):
        user, auth_token = _create_and_authorize_user(client)
        data = {
            'first_name': "Tom",
            'last_name': "Cruise",
            "email": 'test@example.com'
        }
        profile_url = reverse('api:v1:client:client-profile')

        response = client.post(profile_url, data=data, HTTP_AUTHORIZATION=auth_token)
        assert (response.status_code == status.HTTP_201_CREATED)
        data = response.data
        assert (data['first_name'] == 'Tom')
        assert (data['last_name'] == 'Cruise')
        updated_data = {
            'first_name': "Tommy"
        }

        response = client.patch(profile_url, data=json.dumps(updated_data),
                                HTTP_AUTHORIZATION=auth_token,
                                content_type='application/json')
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert (data['first_name'] == 'Tommy')
        assert (data['last_name'] == 'Cruise')


class TestPreferredStylist:

    @pytest.mark.django_db
    def test_add_preferred_stylists(self, client, stylist_data: Stylist):
        user, auth_token = _create_and_authorize_user(client)
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
    def test_delete_preferred_stylist(self, client, stylist_data: Stylist):
        user, auth_token = _create_and_authorize_user(client)
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


class TestSearchStylist:
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
