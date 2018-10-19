from datetime import timedelta

import pytest

from django.urls import reverse
from django.utils import timezone

from django_dynamic_fixture import G
from rest_framework import status

from core.models import PhoneSMSCodes, User
from core.types import UserRole
from integrations.twilio import render_one_time_sms_for_phone
from salon.models import Invitation, Stylist


def get_code(expired=False, redeemed=False, role=UserRole.CLIENT):
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
             role=role
             )
    return code


class TestSendCodeView(object):

    @pytest.mark.django_db
    def test_send_code_for_new_number(self, client, mocker):
        sms_mock = mocker.patch('core.models.send_sms_message')
        data = {
            'phone': '+19876543210'
        }
        sendcode_url = reverse('api:v1:auth:send-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        code = PhoneSMSCodes.objects.last()
        message = render_one_time_sms_for_phone(code.code)
        sms_mock.assert_called_once_with(
            to_phone=data['phone'],
            role=UserRole.CLIENT.value,
            body=message
        )
        data = {
            'phone': '+19876543211',
            'role': UserRole.STYLIST
        }
        sms_mock.reset_mock()
        sendcode_url = reverse('api:v1:auth:send-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        code = PhoneSMSCodes.objects.last()
        message = render_one_time_sms_for_phone(code.code)
        sms_mock.assert_called_once_with(
            to_phone=data['phone'],
            role=UserRole.STYLIST.value,
            body=message
        )

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

    @pytest.mark.django_db
    @pytest.mark.parametrize('role', [UserRole.CLIENT, UserRole.STYLIST])
    def test_code_successive_attempt(self, client, role):
        phone_number = '+19876543210'
        data = {
            'phone': phone_number,
            'role': role
        }
        sendcode_url = reverse('api:v1:auth:send-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        assert (PhoneSMSCodes.objects.all().count() == 1)
        code = PhoneSMSCodes.objects.last().code

        # try sending code for the second time
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        assert(PhoneSMSCodes.objects.all().count() == 1)

        data = {
            'phone': phone_number,
            'code': code,
            'role': role
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert(status.is_success(response.status_code))


class TestVerifyCodeView(object):

    @pytest.mark.django_db
    def test_verify_correct_code(self, client):
        code = get_code(role=UserRole.CLIENT)
        data = {
            'phone': code.phone,
            'code': code.code,
            'role': UserRole.STYLIST
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_400_BAD_REQUEST)
        user = User.objects.last()
        assert (user is None)
        data = {
            'phone': code.phone,
            'code': code.code,
            'role': UserRole.CLIENT
        }
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        user = User.objects.last()
        assert (user.client is not None)

    @pytest.mark.django_db
    def test_verify_client_creation(self, client, stylist_data: Stylist):
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
        assert(user.phone == data['phone'])

    @pytest.mark.django_db
    def test_verify_stylist_creation(self, client):
        code = get_code(role=UserRole.STYLIST)
        data = {
            'phone': code.phone,
            'code': code.code,
            'role': UserRole.STYLIST
        }
        sendcode_url = reverse('api:v1:auth:verify-code')
        response = client.post(sendcode_url, data=data)
        assert (response.status_code == status.HTTP_200_OK)
        user = User.objects.last()
        assert(user)
        assert(user.phone == code.phone)
        assert(user.is_stylist())
        stylist = user.stylist
        assert (stylist is not None)

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
