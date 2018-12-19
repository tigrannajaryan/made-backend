import mock
import pytest

from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status

from core.models import User
from notifications.models import Notification, NotificationChannel


class TestTwilioWebhooks(object):

    def test_auth_header_required(self, client):
        url = reverse('api:v1:webhooks:update-sms-status')
        response = client.post(url, {
            'MessageStatus': 'failed',
            'MessageSid': 'another-sms-id'
        })
        assert(response.status_code == status.HTTP_403_FORBIDDEN)

    @pytest.mark.django_db
    @mock.patch('integrations.twilio.decorators.RequestValidator')
    def test_update_sms_status(self, request_validator_mock, client):
        request_validator_mock.return_value.validate.return_value = True
        user = G(User, phone='12345')
        notification: Notification = G(
            Notification, sent_via_channel=NotificationChannel.SMS,
            twilio_message_id='sms-id',
            destination='12345', user=user,
            device_acked_at=None
        )
        url = reverse('api:v1:webhooks:update-sms-status')
        response = client.post(url, {
            'MessageStatus': 'delivered',
            'MessageSid': 'sms-id',
            'To': '12345'
        }, HTTP_X_TWILIO_SIGNATURE='qwerty')

        notification.refresh_from_db()
        assert(response.status_code == status.HTTP_204_NO_CONTENT)
        assert(notification.device_acked_at is not None)

    @pytest.mark.django_db
    @mock.patch('integrations.twilio.decorators.RequestValidator')
    def test_handle_stop_sms(self, request_validator_mock, client):
        request_validator_mock.return_value.validate.return_value = True
        user: User = G(User, phone='+16135555555', user_stopped_sms=False)
        url = reverse('api:v1:webhooks:handle-sms-reply')
        response = client.post(url, {
            'From': '6135555555',
            'Body': 'stop',
        }, HTTP_X_TWILIO_SIGNATURE='qwerty')
        assert(status.is_success(response.status_code))
        user.refresh_from_db()
        assert(user.user_stopped_sms is True)

    @pytest.mark.django_db
    @mock.patch('integrations.twilio.decorators.RequestValidator')
    def test_handle_start_sms(self, request_validator_mock, client):
        request_validator_mock.return_value.validate.return_value = True
        user: User = G(User, phone='+16135555555', user_stopped_sms=True)
        url = reverse('api:v1:webhooks:handle-sms-reply')
        response = client.post(url, {
            'From': '6135555555',
            'Body': 'start',
        }, HTTP_X_TWILIO_SIGNATURE='qwerty')
        assert (status.is_success(response.status_code))
        user.refresh_from_db()
        assert (user.user_stopped_sms is False)
