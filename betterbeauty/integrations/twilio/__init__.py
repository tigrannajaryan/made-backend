import logging
from typing import Optional

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse
from rest_framework import status

from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.rest import Client

from core.exceptions.middleware import HttpCodeException
from integrations.slack import send_slack_twilio_message_notification

logger = logging.getLogger(__name__)


class TwilioSuppressedException(TwilioException):
    pass


def render_one_time_sms_for_phone(code: str):
    return render_to_string(
        'sms/twilio_sms_code.txt',
        context={
            'code': code
        }
    )


def send_sms_message(
        to_phone: str, body: str, role: str
) -> Optional[str]:
    result_sid: Optional[str] = None
    errors_to_suppress = [
        'Permission to send an SMS has not been enabled for the region',
    ]
    if settings.TWILIO_SMS_ENABLED:
        try:
            client = Client()
            status_callback_url = '{0}{1}'.format(
                settings.BASE_URL,
                reverse('api:v1:webhooks:update-sms-status')
            )
            result = client.messages.create(
                to=to_phone,
                from_=settings.TWILIO_FROM_TEL,
                body=body,
                status_callback=status_callback_url
            )
            result_sid = result.sid
        except (TwilioException, TwilioRestException) as e:
            for error_to_suppress in errors_to_suppress:
                if str(e).find(error_to_suppress) >= 0:
                    # this is a known error that we want to suppress, log it and
                    # re-raise to be caught on the outer level and handled differently
                    # from a common Twilio error
                    logger.warning('Cannot send SMS through twilio', exc_info=True)
                    raise TwilioSuppressedException()
            logger.exception('Cannot send SMS through twilio', exc_info=True)
            raise HttpCodeException(status_code=status.HTTP_504_GATEWAY_TIMEOUT)
    if settings.TWILIO_SLACK_MOCK_ENABLED:
        try:
            send_slack_twilio_message_notification(
                from_phone=settings.TWILIO_FROM_TEL,
                to_phone=to_phone,
                message=body
            )
        except:  # noqa
            # we really don't want this to break the flow for whatever reason
            logger.exception('Could not send Slack message')
    return result_sid
