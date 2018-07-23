from datetime import timedelta

import mock
import pytest

from django.urls import reverse
from django.utils import timezone

from django_dynamic_fixture import G
from rest_framework import status

from client.models import PhoneSMSCodes
from core.models import User
from core.types import UserRole
from salon.models import Invitation, Stylist


def get_code(expired=False, redeemed=False):
    generated_time = timezone.now() - timedelta(minutes=10)
    if expired:
        generated_time = timezone.now() - timedelta(days=1)
    redeemed_time = None
    if redeemed:
        redeemed_time = generated_time + timedelta(minutes=5)
    code = G(PhoneSMSCodes,
             phone='+19876543210',
             generated_at=generated_time,
             redeemed_at=redeemed_time,
             expires_at=generated_time + timedelta(minutes=30),
             )
    return code


class TestSendCodeView(object):

    @pytest.mark.django_db
    def test_send_code_for_new_number(self, client):
        data = {
            'phone': +19876543210
        }
        sendcode_url = reverse('api:v1:auth:send-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)

    @pytest.mark.django_db
    def test_send_code_for_existing_number(self, client):
        phone_number = '+19876543210'
        code = G(PhoneSMSCodes,
                 phone=phone_number,
                 generated_at=timezone.now() - timedelta(days=1, minutes=30),
                 redeemed_at=timezone.now() - timedelta(days=1, minutes=25),
                 expires_at=timezone.now() - timedelta(days=1),
                 )
        data = {
            'phone': phone_number
        }
        sendcode_url = reverse('api:v1:auth:send-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        new_code = PhoneSMSCodes.objects.last()
        assert (new_code is not code.code)
        assert (new_code.redeemed_at is None)


class TestVerifyCodeView(object):

    @pytest.mark.django_db
    def test_verify_correct_code(self, client):
        code = get_code()
        data = {
            'phone': code.phone,
            'code': code.code
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        user = User.objects.last()
        assert (user.client is not None)

    @pytest.mark.django_db
    def test_verify_client_of_stylist_creation(self, client, stylist_data: Stylist):
        code = get_code()
        G(Invitation, stylist=stylist_data, phone=code.phone)
        data = {
            'phone': code.phone,
            'code': code.code
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        user = User.objects.last()
        client = user.client
        assert (client is not None)
        client_of_stylist = client.clientofstylist_set.last()
        assert (client_of_stylist.phone == code.phone)
        assert (client_of_stylist.stylist == stylist_data)

    @pytest.mark.django_db
    def test_verify_incorrect_code(self, client):
        code = get_code()
        data = {
            'phone': code.phone,
            'code': PhoneSMSCodes.generate_code()
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert ('code' in response.data['field_errors'])

    @pytest.mark.django_db
    def test_verify_expired_code(self, client):
        code = get_code(expired=True)
        data = {
            'phone': code.phone,
            'code': code.code
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert ('code' in response.data['field_errors'])

    @pytest.mark.django_db
    def test_verify_redeemed_code(self, client):
        code = get_code(redeemed=True)
        data = {
            'phone': code.phone,
            'code': code.code
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert ('code' in response.data['field_errors'])


class TestRegisterUserView(object):

    @pytest.mark.django_db
    def test_register_stylist_user(self, client):
        data = {
            'email': 'user@example.com',
            'password': 'mypassword',
            'role': UserRole.STYLIST
        }
        register_url = reverse('api:v1:auth:register')
        response = client.post(register_url, data=data)
        assert(response.status_code == status.HTTP_200_OK)
        data = response.data
        assert(data['token'] is not None)
        assert(data['profile'] is not None)
        user = User.objects.last()
        assert(user and user.email == 'user@example.com')
        assert(UserRole.STYLIST in user.role)
        assert(user.stylist is not None)

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
        assert('email' in response.data['field_errors'])

    @pytest.mark.django_db
    def test_register_forbidden_role(self, client):
        data = {
            'email': 'user@example.com',
            'password': 'mypassword',
            'role': UserRole.STAFF
        }
        register_url = reverse('api:v1:auth:register')
        response = client.post(register_url, data=data)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)


class TestFBRegisterLoginView(object):

    @mock.patch('api.v1.auth.views.verify_fb_token', lambda a, b: True)
    @pytest.mark.django_db
    def test_login_existing_user(self, client):
        fb_login_url = reverse('api:v1:auth:get_fb_token')
        user = G(User, facebook_id='12345', role=[UserRole.STYLIST])
        stylist = G(Stylist, user=user)
        data = {
            'fbAccessToken': 'abcd12345',
            'fbUserID': '12345',
            'role': UserRole.STYLIST
        }
        response = client.post(fb_login_url, data=data)
        assert(response.status_code == status.HTTP_200_OK)
        data = response.data
        assert('token' in data)
        profile_data = data['profile']
        assert(profile_data['id'] == stylist.id)

    @mock.patch('api.v1.auth.views.verify_fb_token', lambda a, b: True)
    @mock.patch('core.utils.facebook.get_profile_data', lambda a, user_id: {
        'email': 'email@example.com',
        'first_name': 'Jane',
        'last_name': 'McBob',
    })
    @pytest.mark.django_db
    def test_register_new_stylist_user(self, client):
        fb_login_url = reverse('api:v1:auth:get_fb_token')
        data = {
            'fbAccessToken': 'abcd12345',
            'fbUserID': '12345',
            'role': UserRole.STYLIST,
        }
        response = client.post(fb_login_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        data = response.data
        assert ('token' in data)
        profile_data = data['profile']
        created_stylist = Stylist.objects.last()
        assert (profile_data['id'] == created_stylist.id)
        assert (created_stylist.available_days.count() == 7)
        user = created_stylist.user
        assert(user.first_name == 'Jane')
        assert(user.last_name == 'McBob')
        assert(UserRole.STYLIST in user.role)
