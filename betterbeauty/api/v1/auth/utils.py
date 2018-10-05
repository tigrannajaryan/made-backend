from typing import Optional
from uuid import uuid4

import phonenumbers
from django.db import transaction
from phonenumbers import region_code_for_number

from client.models import Client, ClientOfStylist
from core.models import User
from core.types import UserRole
from salon.models import Invitation
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
    client = Client.objects.create(user=user, country=region)
    current_stylists = []
    # get all client_of_stylists and link with client profile
    client_of_stylists = ClientOfStylist.objects.filter(phone=user.phone)
    for client_of_stylist in client_of_stylists:
        current_stylists.append(client_of_stylist.stylist_id)
        client_of_stylist.client = client
        client_of_stylist.save(update_fields=['client'])
    # create client_of_stylists for invitations from new stylists
    invitations = Invitation.objects.filter(phone=user.phone)
    for invitation in invitations:
        if invitation.stylist_id not in current_stylists:
            ClientOfStylist.objects.create(
                first_name=user.first_name,
                last_name=user.last_name,
                client=client,
                phone=user.phone,
                stylist=invitation.stylist,
            )
            current_stylists.append(invitation.stylist_id)
    return user


def get_country_code_from_phone(phone_number: str) -> str:
    phone_number = phonenumbers.parse(phone_number)
    return region_code_for_number(phone_number)
