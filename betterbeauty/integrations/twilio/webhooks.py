import logging
from typing import Optional

from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework import status

from core.models import User
from core.utils.phone import to_e164_format
from integrations.slack import (
    send_slack_incoming_twilio_notification,
    send_slack_user_disabled_sms_notifications,
    send_slack_user_enabled_sms_notifications,
)
from integrations.twilio.decorators import twilio_auth_required
from notifications.models import Notification, NotificationChannel

logger = logging.getLogger(__name__)

TWILIO_DELIVERED_STATUS = 'delivered'

# upon receiving these words (it should be a single word in the message)
# Twilio will add a recipient to a black list of recipients, any further
# attepmt to send an sms through Twilio to this number will not succeed

# more info - https://support.twilio.com/hc/en-us/articles/223134027-Twilio-
#             support-for-opt-out-keywords-SMS-STOP-filtering-

TWILIO_STOP_KEYWORDS = ['stop', 'stopall', 'unsubscribe', 'cancel', 'end', 'quit']
TWILIO_START_KEYWORDS = ['start', 'yes', 'unstop', ]
# make sure there's no intersection between these two
assert not set(TWILIO_STOP_KEYWORDS) & set(TWILIO_START_KEYWORDS)


@csrf_exempt
@require_POST
@twilio_auth_required
def update_sms_status(request):
    """
    This hook will be called by Twilio when a message state changes.
    If message state is set to `delivered` this means that cellular
    network have confirmed that a message was delivered to end user's
    device, so we can capture this in device_acked_at field of the
    Notification
    """
    message_id = request.POST['MessageSid']

    notification: Notification = Notification.objects.filter(
        twilio_message_id=message_id,
        sent_via_channel=NotificationChannel.SMS
    ).last()

    if notification:
        message_status = request.POST['MessageStatus']
        if message_status == TWILIO_DELIVERED_STATUS:
            notification.device_acked_at = timezone.now()
            notification.save(update_fields=['device_acked_at', ])

    return HttpResponse(status=status.HTTP_204_NO_CONTENT)


@csrf_exempt
@require_POST
@twilio_auth_required
def handle_sms_reply(request):
    """
    This webhook will be called by Twilio when an incoming SMS message
    is received. We will look up a user by recipient's phone.

    Although we can handle all sorts of things in this webhook (e.g. send
    a meaningful response to the customer, e.g. 'Thanks', 'We'll call you back',
    etc., for now, in this webhook we will only be handling users' requests
    to unsubscribe or resume subscription. When twilio receives a message constituting only of
    one word from TWILIO_STOP_KEYWORDS list, it will blacklist sending
    messages to the user, but will also call the webhook, so that we could
    gracefully handle the situation.

    There's no need to send anything in response since Twilio won't permit it
    anyway - user is already blacklisted. So we'll just save this fact into
    the User object, which will prevent from getting messages from the user in the
    future
    """
    from_tel = to_e164_format(request.POST['From'])
    body = str(request.POST['Body']).strip().lower()
    user: Optional[User] = User.objects.filter(phone=from_tel).last()
    if not user:
        return HttpResponse(status=status.HTTP_204_NO_CONTENT)
    send_slack_incoming_twilio_notification(user, body)
    if body in TWILIO_STOP_KEYWORDS:
        user.user_stopped_sms = True
        user.save(update_fields=['user_stopped_sms', ])
        send_slack_user_disabled_sms_notifications(user)
    if body in TWILIO_START_KEYWORDS:
        user.user_stopped_sms = False
        user.save(update_fields=['user_stopped_sms', ])
        send_slack_user_enabled_sms_notifications(user)
        # TODO: perhaps we could sent some response here, e.g. Thanks note
    return HttpResponse(status=status.HTTP_204_NO_CONTENT)
