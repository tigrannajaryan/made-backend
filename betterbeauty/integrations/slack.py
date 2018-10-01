import logging

from django.conf import settings
from django.template.loader import render_to_string

from requests.exceptions import HTTPError
from slackweb import Slack

from core.constants import EnvLevel

logger = logging.getLogger(__name__)


def send_slack_twilio_message_notification(from_phone, to_phone, message):
    slack = Slack(url=settings.TWILLIO_SLACK_HOOK)

    # TODO: update context with stylist and client

    message = render_to_string(
        'slack/twilio_message_notification.txt',
        context={
            'from_phone': from_phone,
            'to_phone': to_phone,
            'message': message,
        })
    try:
        slack.notify(
            text=message,
            channel=settings.TWILLIO_SLACK_CHANNEL,
            username='twilio-bot',
        )
    except HTTPError:
        if settings.LEVEL != EnvLevel.PRODUCTION:
            raise
        logger.exception('Failed to send Slack message', exc_info=True)
