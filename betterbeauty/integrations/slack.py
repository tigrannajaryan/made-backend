from django.conf import settings
from django.template.loader import render_to_string


from slackweb import Slack


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
    slack.notify(
        text=message,
        channel=settings.TWILLIO_SLACK_CHANNEL,
        username='twilio-bot',
    )
