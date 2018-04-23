import pytest

from rest_framework import status

from django_dynamic_fixture import G

from django.urls import reverse

from core.choices import USER_ROLE
from core.models import User
from salon.models import Stylist


class TestStylistView(object):

    def _create_and_authorize_user(self, client):
        user = G(
            User, email='email@example.com', first_name='Jane', last_name='McBob',
            role=USER_ROLE.stylist
        )
        user.set_password('password')
        user.save()
        auth_url = reverse('api:v1:auth:get_jwt_token')
        data = client.post(
            auth_url, data={'email': 'email@example.com', 'password': 'password'}
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
        assert(data['id'] == stylist.id)

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
