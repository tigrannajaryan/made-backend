import logging
from typing import Any, Dict, Optional, Tuple, Union

from django.db import transaction
from push_notifications import NotificationError
from push_notifications.models import APNSDevice, GCMDevice

from core.models import User
from core.types import UserRole
from .types import (
    MobileAppIdType,
    PushRegistrationIdType,
)

logger = logging.getLogger(__name__)


def get_device_db_model_klass(
        registration_id_type: PushRegistrationIdType
) -> Union[APNSDevice, GCMDevice]:
    """Return DB model class used for storing device information"""
    return {
        PushRegistrationIdType.APNS: APNSDevice,
        PushRegistrationIdType.FCM: GCMDevice
    }[registration_id_type]


def get_application_id_for_device_type_and_role(
        registration_id_type: PushRegistrationIdType,
        user_role: UserRole,
        is_development_build: bool
) -> MobileAppIdType:
    """
    Return application type (MobileAppIdType) based on token type and user role
    and which certificate application is built with (development or distribution
    certificates are the options).

    :param registration_id_type: token type (apns/fcm)
    :param user_role: user role (client/stylist)
    :param is_development_build: True if application built with development certificate
    :return: MobileAppIdType application id
    """
    if not is_development_build:
        return {
            PushRegistrationIdType.APNS: {
                UserRole.STYLIST: MobileAppIdType.IOS_STYLIST,
                UserRole.CLIENT: MobileAppIdType.IOS_CLIENT
            },
            PushRegistrationIdType.FCM: {
                UserRole.STYLIST: MobileAppIdType.ANDROID_STYLIST,
                UserRole.CLIENT: MobileAppIdType.ANDROID_CLIENT
            },
        }[registration_id_type][user_role]
    return {
        PushRegistrationIdType.APNS: {
            UserRole.STYLIST: MobileAppIdType.IOS_STYLIST_DEV,
            UserRole.CLIENT: MobileAppIdType.IOS_CLIENT_DEV
        },
        PushRegistrationIdType.FCM: {
            UserRole.STYLIST: MobileAppIdType.ANDROID_STYLIST,
            UserRole.CLIENT: MobileAppIdType.ANDROID_CLIENT
        },
    }[registration_id_type][user_role]


def register_device(
        user: User, user_role: UserRole, registration_id: str,
        registration_id_type: PushRegistrationIdType,
        is_development_build: bool=False
) -> Tuple[Union[APNSDevice, GCMDevice], bool]:
    """
    Create either APNSDevice or GCMDevice entry (if doesn't exist yet)
    for a device of a given user. If the device was previously registered
    with any other user - this registration is deleted.

    :param user: User record to associate device with
    :param user_role: role of the user/application (stylist or client)
    :param registration_id: APNS token or FCM registration id
    :param registration_id_type: type of registration id (apns / fcm)
    :param is_development_build: True if application built with development
    certificate
    :return: DB object representing device and creation flag
    """
    model = get_device_db_model_klass(registration_id_type)

    registration_id = registration_id.replace(' ', '')
    application_id = get_application_id_for_device_type_and_role(
        registration_id_type=registration_id_type,
        user_role=user_role, is_development_build=is_development_build
    )
    with transaction.atomic():
        # if the device was previously registered with different user - delete it
        model.objects.filter(
            registration_id=registration_id,
        ).exclude(user=user).delete()
        if registration_id_type == PushRegistrationIdType.FCM:
            device, created = model.objects.get_or_create(
                user=user, registration_id=registration_id,
                application_id=application_id,
                cloud_message_type='FCM'
            )
        else:
            device, created = model.objects.get_or_create(
                user=user, registration_id=registration_id,
                application_id=application_id
            )
    return device, created


def unregister_device(
        user: User, user_role: UserRole, registration_id: str,
        registration_id_type: PushRegistrationIdType,
        is_development_build: bool=False
) -> bool:
    """
    Delete either APNSDevice or GCMDevice entry for a device of a given user
    :param user: user: User record of a user to whom the device belongs
    :param user_role: role of the user/application (stylist or client)
    :param registration_id: APNS token or FCM registration id
    :param registration_id_type: type of registration id (apns / fcm)
    :param is_development_build: True if application built with development
    certificate
    :return: True if device was deleted, False otherwise
    """
    model = get_device_db_model_klass(registration_id_type)

    registration_id = registration_id.replace(' ', '')
    application_id = get_application_id_for_device_type_and_role(
        registration_id_type=registration_id_type,
        user_role=user_role, is_development_build=is_development_build
    )

    deleted_count, _ = model.objects.filter(
        user=user, registration_id=registration_id,
        application_id=application_id
    ).delete()
    if deleted_count > 0:
        return True
    logger.warning(
        'Could not unregister {0} device {1} for user {2}, '
        'device registration is not found'.format(
            registration_id_type, registration_id, user.uuid
        )
    )
    return False


def send_message_to_apns_devices_of_user(
        user: User, user_role: UserRole, message: str,
        extra: Dict[str, Any], badge_count: Optional[int]=0
):
    """
        Bulk send message to all configured APNS installed apps matching target
        :param user: User to whom devices belong
        :param user_role: Type of application (client/stylist)
        :param message: Text of the message
        :param extra: Dictionary with arbitrary data to attach to payload
        :param badge_count: positive int number to display on badge; 0 clears the badge
        :return: True if operation was successful, False otherwise
    """
    eligible_app_ids = {
        UserRole.STYLIST: [MobileAppIdType.IOS_STYLIST, MobileAppIdType.IOS_STYLIST_DEV],
        UserRole.CLIENT: [MobileAppIdType.IOS_CLIENT, MobileAppIdType.IOS_CLIENT_DEV]
    }[user_role]
    apns_devices = user.apnsdevice_set.filter(
        application_id__in=eligible_app_ids, active=True)
    try:
        apns_devices.send_message(message=message, extra=extra, badge=badge_count)
    except NotificationError:
        logger.exception('Failed APNS notification(s) to {0} user {1}'.format(
            user_role, user.uuid
        ))


def send_message_to_fcm_devices_of_user(
        user: User, user_role: UserRole, message: str,
        extra: Dict[str, Any], badge_count: Optional[int]=0
):
    """
    Bulk send message to all configured GCM/FCM installed apps matching target
    :param user: User to whom devices belong
    :param user_role: Type of application (client/stylist)
    :param message: Text of the message
    :param extra: Dictionary with arbitrary data to attach to payload
    :param badge_count: positive int number to display on badge; 0 clears the badge
    :return: True if operation was successful, False otherwise
    """
    eligible_app_ids = {
        UserRole.STYLIST: [MobileAppIdType.ANDROID_STYLIST, ],
        UserRole.CLIENT: [MobileAppIdType.ANDROID_CLIENT, ]
    }[user_role]
    # Based on django_push_notifications documentation, we should specifically add
    # this filter (`cloud_message_type='FCM'`)
    fcm_devices = user.gcmdevice_set.filter(
        application_id__in=eligible_app_ids, active=True, cloud_message_type='FCM')
    try:
        # Although we're dealing with FCM here, pure FCM format doesn't seem to work,
        # so here we're rolling back to native GCM and adding `body` key to extra, so
        # that it will end up in the payload's `data` part. More info can be found at
        # https://github.com/jazzband/django-push-notifications/blob/
        # 8c73a77131be2259f961a997cc3ca8945028f519/README.rst#
        # firebase-vs-google-cloud-messaging
        extra.update({'body': message})
        fcm_devices.send_message(
            message=None, extra=extra, badge=badge_count, use_fcm_notifications=False
        )
        return True
    except NotificationError:
        logger.exception('Failed FCM notification(s) to {0} user {1}'.format(
            user_role, user.uuid
        ))
        return False
