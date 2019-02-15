from model_utils import Choices

from core.types import StrEnum


class NotificationChannel(StrEnum):
    SMS = 'sms'
    PUSH = 'push'
    EMAIL = 'email'


NOTIFICATION_CNANNEL_CHOICES = Choices(
    (NotificationChannel.SMS.value, 'sms', 'SMS message'),
    (NotificationChannel.PUSH.value, 'push', 'Push Notification'),
)


class NotificationCode(StrEnum):
    HINT_TO_FIRST_BOOK = 'hint_to_first_book'
    HINT_TO_SELECT_STYLIST = 'hint_to_select_stylist'
    HINT_TO_REBOOK = 'hint_to_rebook'
    NEW_APPOINTMENT = 'new_appointment'
    TOMORROW_APPOINTMENTS = 'tomorrow_appointments'
    REGISTRATION_INCOMPLETE = 'registration_incomplete'
    REMIND_DEFINE_SERVICES = 'remind_define_services'
    STYLIST_CANCELLED_APPOINTMENT = 'stylist_cancelled_appointment'
    CLIENT_CANCELLED_APPOINTMENT = 'client_cancelled_appointment'
    REMIND_INVITE_CLIENTS = 'remind_invite_clients'
    REMIND_ADD_PHOTO = 'remind_add_photo'
    REMIND_DEFINE_HOURS = 'remind_define_hours'
    REMIND_DEFINE_DISCOUNTS = 'remind_define_disounts'
    DEAL_OF_THE_WEEK = 'deal_of_the_week'
    DEAL_OF_THE_WEEK_PROMO = 'deal_of_the_week_promo'
    INVITE_YOUR_STYLIST = 'invite_your_stylist'
    CLIENT_REGISTRATION_INCOMPLETE = 'client_registration_incomplete'
    RESCHEDULED_APPOINTMENT = 'rescheduled_appointment'
    APPEARED_IN_SEARCH = 'client_appeared_in_search'
