from django.conf import settings

from core.constants import EnvLevel
from notifications.types import NotificationChannel, NotificationCode

# TODO: set proper priorities

# Priority of delivery channel for given notification code. First
# available channel will be used. E.g. if [Push, SMS] are set, we'll
# first check if push devices are available. If there are - we'll send
# the message via PUSH, and won't send it over SMS. If no PUSH devices
# are configured - we'll send over SMS

if settings.LEVEL == EnvLevel.PRODUCTION:
    NOTIFICATION_CHANNEL_PRIORITY = {
        NotificationCode.HINT_TO_FIRST_BOOK: [
            NotificationChannel.PUSH, NotificationChannel.SMS,
        ],
        NotificationCode.HINT_TO_SELECT_STYLIST: [
            NotificationChannel.PUSH, NotificationChannel.SMS,
        ],
        NotificationCode.HINT_TO_REBOOK: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.NEW_APPOINTMENT: [
            NotificationChannel.PUSH, NotificationChannel.SMS,
        ],
        NotificationCode.TOMORROW_APPOINTMENTS: [
            NotificationChannel.PUSH  # NotificationChannel.SMS
        ],
        NotificationCode.REGISTRATION_INCOMPLETE: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.STYLIST_CANCELLED_APPOINTMENT: [
            NotificationChannel.PUSH  # NotificationChannel.SMS
        ],
        NotificationCode.CLIENT_CANCELLED_APPOINTMENT: [
            NotificationChannel.PUSH  # NotificationChannel.SMS
        ],
        NotificationCode.REMIND_INVITE_CLIENTS: [
            NotificationChannel.PUSH, NotificationChannel.EMAIL, NotificationChannel.SMS
        ],
        NotificationCode.REMIND_DEFINE_SERVICES: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.REMIND_DEFINE_HOURS: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.REMIND_ADD_PHOTO: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.REMIND_DEFINE_DISCOUNTS: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.DEAL_OF_THE_WEEK: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.DEAL_OF_THE_WEEK_PROMO: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.INVITE_YOUR_STYLIST: [
            NotificationChannel.SMS, NotificationChannel.EMAIL, NotificationChannel.PUSH
        ],
        NotificationCode.CLIENT_REGISTRATION_INCOMPLETE: [
            NotificationChannel.PUSH
        ],
        NotificationCode.APPEARED_IN_SEARCH: [
            NotificationChannel.PUSH, NotificationChannel.EMAIL, NotificationChannel.SMS
        ],
        NotificationCode.RESCHEDULED_APPOINTMENT: [
            NotificationChannel.PUSH, NotificationChannel.EMAIL, NotificationChannel.SMS
        ],
        NotificationCode.STYLIST_PAYOUT_PROMO: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
    }
else:
    NOTIFICATION_CHANNEL_PRIORITY = {
        NotificationCode.HINT_TO_FIRST_BOOK: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.HINT_TO_SELECT_STYLIST: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.HINT_TO_REBOOK: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.NEW_APPOINTMENT: [
            NotificationChannel.PUSH, NotificationChannel.SMS,
        ],
        NotificationCode.TOMORROW_APPOINTMENTS: [
            NotificationChannel.PUSH  # NotificationChannel.SMS
        ],
        NotificationCode.REGISTRATION_INCOMPLETE: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.STYLIST_CANCELLED_APPOINTMENT: [
            NotificationChannel.PUSH  # NotificationChannel.SMS
        ],
        NotificationCode.CLIENT_CANCELLED_APPOINTMENT: [
            NotificationChannel.PUSH  # NotificationChannel.SMS
        ],
        NotificationCode.REMIND_INVITE_CLIENTS: [
            NotificationChannel.PUSH, NotificationChannel.EMAIL, NotificationChannel.SMS
        ],
        NotificationCode.REMIND_ADD_PHOTO: [
            NotificationChannel.PUSH, NotificationChannel.SMS,
        ],
        NotificationCode.REMIND_DEFINE_SERVICES: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.REMIND_DEFINE_HOURS: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.REMIND_DEFINE_DISCOUNTS: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.DEAL_OF_THE_WEEK: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.DEAL_OF_THE_WEEK_PROMO: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
        NotificationCode.INVITE_YOUR_STYLIST: [
            NotificationChannel.SMS, NotificationChannel.EMAIL, NotificationChannel.PUSH
        ],
        NotificationCode.CLIENT_REGISTRATION_INCOMPLETE: [
            NotificationChannel.PUSH
        ],
        NotificationCode.APPEARED_IN_SEARCH: [
            NotificationChannel.PUSH, NotificationChannel.EMAIL, NotificationChannel.SMS
        ],
        NotificationCode.RESCHEDULED_APPOINTMENT: [
            NotificationChannel.PUSH, NotificationChannel.EMAIL, NotificationChannel.SMS
        ],
        NotificationCode.STYLIST_PAYOUT_PROMO: [
            NotificationChannel.PUSH, NotificationChannel.SMS
        ],
    }
