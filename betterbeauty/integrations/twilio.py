import logging

from django.conf import settings
from django.template.loader import render_to_string

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from .slack import send_slack_twilio_message_notification

logger = logging.getLogger(__name__)


def render_one_time_sms_for_phone(code: str):
    return render_to_string(
        'sms/twilio_sms_code.txt',
        context={
            'code': code
        }
    )


def send_sms_message(to_phone: str, body: str, status_callback=None):
    # TODO: implement status callback handler
    if settings.TWILIO_SMS_ENABLED:
        client = Client()
        try:
            result = client.messages.create(
                to=to_phone,
                from_=settings.TWILIO_FROM_TEL,
                body=body,
                status_callback=status_callback
            )
            return result.sid
        except TwilioRestException:
            logger.info('Cannot send SMS through twilio', exc_info=True)
    if settings.TWILIO_SLACK_MOCK_ENABLED:
        send_slack_twilio_message_notification(
            from_phone=settings.TWILIO_FROM_TEL,
            to_phone=to_phone,
            message=body
        )
