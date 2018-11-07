from model_utils import Choices

from core.types import StrEnum


class PushRegistrationIdType(StrEnum):
    APNS = 'apns'
    FCM = 'fcm'


PUSH_NOTIFICATION_TOKEN_CHOICES = Choices(
    (PushRegistrationIdType.APNS, 'apns', 'apns'),
    (PushRegistrationIdType.FCM, 'fcm', 'fcm'),
)


class MobileAppIdType(StrEnum):
    IOS_CLIENT = 'ios_client'  # client app built with distribution cert (TF / AppStore)
    IOS_STYLIST = 'ios_stylist'  # stylist app built with distribution cert (TF / AppStore)
    IOS_CLIENT_DEV = 'ios_client_dev'  # client app built with dev cert (local build)
    IOS_STYLIST_DEV = 'ios_stylist_dev'  # stylist app built with dev cert (local build)
    ANDROID_CLIENT = 'android_client'
    ANDROID_STYLIST = 'android_stylist'
