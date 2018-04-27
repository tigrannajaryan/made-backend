import pytest
import mock

from django_dynamic_fixture import G

from rest_framework import status

from django.urls import reverse

from core.choices import USER_ROLE
from core.models import User
from salon.models import Stylist


class TestRegisterUserView(object):

    @pytest.mark.django_db
    def test_register_user(self, client):
        data = {
            'email': 'user@example.com',
            'password': 'mypassword',
        }
        register_url = reverse('api:v1:auth:register')
        response = client.post(register_url, data=data)
        assert(response.status_code == status.HTTP_200_OK)
        data = response.data
        assert(data['token'] is not None)
        assert(data['stylist'] is None)
        user = User.objects.last()
        assert(user and user.email == 'user@example.com')
        assert(user.role == USER_ROLE.stylist)

    @pytest.mark.django_db
    def test_register_existing_user(self, client):
        G(User, email='user@example.com')
        data = {
            'email': 'user@example.com',
            'password': 'mypassword',
        }
        register_url = reverse('api:v1:auth:register')
        response = client.post(register_url, data=data)
        assert(response.status_code == status.HTTP_400_BAD_REQUEST)
        assert('email' in response.data)


class TestFBRegisterLoginView(object):

    @mock.patch('api.v1.auth.views.verify_fb_token', lambda a, b: True)
    @pytest.mark.django_db
    def test_login_existing_user(self, client):
        fb_login_url = reverse('api:v1:auth:get_fb_token')
        user = G(User, facebook_id='12345', role=USER_ROLE.stylist)
        stylist = G(Stylist, user=user)
        data = {
            'fbAccessToken': 'abcd12345',
            'fbUserID': '12345'
        }
        response = client.post(fb_login_url, data=data)
        assert(response.status_code == status.HTTP_200_OK)
        data = response.data
        assert('token' in data)
        stylist_data = data['stylist']
        assert(stylist_data['id'] == stylist.id)

    @mock.patch('api.v1.auth.views.verify_fb_token', lambda a, b: True)
    @mock.patch('core.utils.facebook.get_profile_data', lambda a, user_id: {
        'email': 'email@example.com',
        'first_name': 'Jane',
        'last_name': 'McBob',
    })
    @pytest.mark.django_db
    def test_register_new_user(self, client):
        fb_login_url = reverse('api:v1:auth:get_fb_token')
        data = {
            'fbAccessToken': 'abcd12345',
            'fbUserID': '12345'
        }
        response = client.post(fb_login_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert ('token' in data)
        stylist_data = data['stylist']
        created_stylist = Stylist.objects.last()
        assert (stylist_data['id'] == created_stylist.id)
        assert (created_stylist.available_days.count() == 7)
        user = created_stylist.user
        assert(user.first_name == 'Jane')
        assert(user.last_name == 'McBob')
        assert(user.role == USER_ROLE.stylist)
