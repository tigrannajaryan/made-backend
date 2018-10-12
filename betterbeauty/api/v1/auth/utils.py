from typing import Optional
from uuid import uuid4

import phonenumbers
from django.db import transaction
from phonenumbers import region_code_for_number

from client.models import Client
from core.models import User
from core.types import UserRole
from salon.utils import create_stylist_profile_for_user


def create_user_from_phone(phone: str, role) -> User:
    bogus_email = 'client-{0}@madebeauty.com'.format(uuid4())
    user = User.objects.create_user(
        email=bogus_email,
        first_name="",
        last_name="",
        phone=phone,
        is_active=True,
        role=[UserRole.CLIENT]
    )
    user.set_unusable_password()
    return user


@transaction.atomic
def create_stylist_profile_from_phone(phone: str, user: Optional[User]=None)-> User:
    if not user:
        user = create_user_from_phone(phone, role=UserRole.STYLIST)
    create_stylist_profile_for_user(user)
    return user


@transaction.atomic
def create_client_profile_from_phone(phone: str, user: Optional[User]=None)-> User:
    if user and UserRole.CLIENT not in user.role:
        user.role.append(UserRole.CLIENT)
        user.save(update_fields=['role'])
    if not user:
        user = create_user_from_phone(phone, UserRole.CLIENT)
    region = get_country_code_from_phone(phone)
    Client.objects.create(user=user, country=region)
    return user


def get_country_code_from_phone(phone_number: str) -> str:
    phone_number = phonenumbers.parse(phone_number)
    return region_code_for_number(phone_number)
