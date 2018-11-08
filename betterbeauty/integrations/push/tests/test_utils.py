import pytest

from django_dynamic_fixture import G
from push_notifications.models import APNSDevice

from core.models import User
from core.types import UserRole

from ..types import MobileAppIdType, PushRegistrationIdType
from ..utils import (
    get_application_id_for_device_type_and_role,
    register_device,
    unregister_device,
)


def test_get_application_id_for_device_type_and_role():
    assert(get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.APNS,
        user_role=UserRole.STYLIST,
        is_development_build=False) == MobileAppIdType.IOS_STYLIST)
    assert(get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.APNS,
        user_role=UserRole.CLIENT,
        is_development_build=False) == MobileAppIdType.IOS_CLIENT)
    assert (get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.FCM,
        user_role=UserRole.STYLIST,
        is_development_build=False) == MobileAppIdType.ANDROID_STYLIST)
    assert (get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.FCM,
        user_role=UserRole.CLIENT,
        is_development_build=False) == MobileAppIdType.ANDROID_CLIENT)
    assert (get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.APNS,
        user_role=UserRole.STYLIST,
        is_development_build=True) == MobileAppIdType.IOS_STYLIST_DEV)
    assert (get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.APNS,
        user_role=UserRole.CLIENT,
        is_development_build=True) == MobileAppIdType.IOS_CLIENT_DEV)
    assert (get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.FCM,
        user_role=UserRole.STYLIST,
        is_development_build=True) == MobileAppIdType.ANDROID_STYLIST)
    assert (get_application_id_for_device_type_and_role(
        registration_id_type=PushRegistrationIdType.FCM,
        user_role=UserRole.CLIENT,
        is_development_build=True) == MobileAppIdType.ANDROID_CLIENT)


@pytest.mark.django_db
def test_register_device():
    token = '7d3a4c02 11e40390 27a5fbd9 0a2e1deb 2f87d527 f003a66a ef6ec404 a371b058'
    token_clarified = '7d3a4c0211e4039027a5fbd90a2e1deb2f87d527f003a66aef6ec404a371b058'
    user: User = G(User)
    device, created = register_device(
        user=user, user_role=UserRole.CLIENT, registration_id=token,
        registration_id_type=PushRegistrationIdType.APNS
    )
    assert(created is True)
    assert(device is not None)
    assert(device.__class__ == APNSDevice)
    assert(device.registration_id == token_clarified)
    assert(device.application_id == MobileAppIdType.IOS_CLIENT)
    assert(device.user == user)
    device, created = register_device(
        user=user, user_role=UserRole.CLIENT, registration_id=token,
        registration_id_type=PushRegistrationIdType.APNS
    )
    assert (created is False)
    assert (device is not None)
    device.delete()
    device, created = register_device(
        user=user, user_role=UserRole.CLIENT, registration_id=token,
        registration_id_type=PushRegistrationIdType.APNS, is_development_build=True
    )
    assert (created is True)
    assert (device is not None)
    assert (device.__class__ == APNSDevice)
    assert (device.registration_id == token_clarified)
    assert (device.application_id == MobileAppIdType.IOS_CLIENT_DEV)
    assert (device.user == user)
    device, created = register_device(
        user=user, user_role=UserRole.CLIENT, registration_id=token,
        registration_id_type=PushRegistrationIdType.APNS, is_development_build=True
    )
    assert (created is False)
    assert (device is not None)


@pytest.mark.django_db
def test_register_and_unregister_existing():
    """Verify that if device is registered with new user, it's unregistered from the old one"""
    token = '7d3a4c0211e4039027a5fbd90a2e1deb2f87d527f003a66aef6ec404a371b058'
    user_previous: User = G(User)
    user_current: User = G(User)
    register_device(
        user=user_previous, user_role=UserRole.CLIENT, registration_id=token,
        registration_id_type=PushRegistrationIdType.APNS
    )
    assert(APNSDevice.objects.filter(user=user_previous).count() == 1)
    assert (APNSDevice.objects.filter(user=user_current).count() == 0)
    register_device(
        user=user_current, user_role=UserRole.STYLIST, registration_id=token,
        registration_id_type=PushRegistrationIdType.APNS
    )
    assert (APNSDevice.objects.filter(user=user_previous).count() == 0)
    assert (APNSDevice.objects.filter(user=user_current).count() == 1)


@pytest.mark.django_db
def test_unregister_device():
    user: User = G(User)
    token = '7d3a4c02 11e40390 27a5fbd9 0a2e1deb 2f87d527 f003a66a ef6ec404 a371b058'
    token_clarified = '7d3a4c0211e4039027a5fbd90a2e1deb2f87d527f003a66aef6ec404a371b058'
    G(
        APNSDevice, registration_id=token_clarified, application_id=MobileAppIdType.IOS_CLIENT_DEV,
        user=user
    )
    assert(APNSDevice.objects.filter(user=user).count() == 1)
    assert(unregister_device(
        user=user, user_role=UserRole.CLIENT,
        registration_id_type=PushRegistrationIdType.APNS, registration_id=token,
    ) is False)
    assert (APNSDevice.objects.filter(user=user).count() == 1)
    assert(unregister_device(
        user=user, user_role=UserRole.CLIENT, registration_id_type=PushRegistrationIdType.APNS,
        registration_id=token, is_development_build=True
    ) is True)
    assert (APNSDevice.objects.filter(user=user).count() == 0)
