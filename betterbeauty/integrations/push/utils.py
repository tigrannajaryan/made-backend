import logging
from typing import Tuple, Union

from django.db import transaction
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
