import logging
from typing import Optional

from django.conf import settings
from django.template.loader import render_to_string
from rest_framework import status

from twilio.base.exceptions import TwilioException, TwilioRestException
from twilio.rest import Client

from core.exceptions.middleware import HttpCodeException
from .slack import send_slack_twilio_message_notification

logger = logging.getLogger(__name__)


def render_one_time_sms_for_phone(code: str):
    return render_to_string(
        'sms/twilio_sms_code.txt',
        context={
            'code': code
        }
    )


def send_sms_message(
        to_phone: str, body: str, role: str, status_callback=None
) -> Optional[str]:
    # TODO: implement status callback handler
    result_sid: Optional[str] = None
    if settings.TWILIO_SMS_ENABLED:
        try:
            client = Client()
            result = client.messages.create(
                to=to_phone,
                from_=settings.TWILIO_FROM_TEL,
                body=body,
                status_callback=status_callback
            )
            result_sid = result.sid
        except TwilioRestException as e:
            logger.exception('Cannot send SMS through twilio', exc_info=True)
            raise HttpCodeException(status_code=status.HTTP_504_GATEWAY_TIMEOUT)
        except TwilioException as e:
            logger.exception('Cannot send SMS through twilio', exc_info=True)
            raise HttpCodeException(status_code=status.HTTP_504_GATEWAY_TIMEOUT)
    if settings.TWILIO_SLACK_MOCK_ENABLED:
        send_slack_twilio_message_notification(
            from_phone=settings.TWILIO_FROM_TEL,
            to_phone=to_phone,
            message=body
        )
    return result_sid
