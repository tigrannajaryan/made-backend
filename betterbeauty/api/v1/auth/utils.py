from uuid import uuid4

from client.models import Client, ClientOfStylist
from core.models import User
from core.types import UserRole
from salon.models import Invitation


def create_client_profile_from_phone(phone, user=None):
    if user and UserRole.CLIENT not in user.role:
        user.role.append(UserRole.CLIENT)
        user.save(update_fields=['role'])
    else:
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

    client = Client.objects.create(user=user)
    invited_stylists = []
    client_of_stylists = ClientOfStylist.objects.filter(phone=user.phone)
    for client_of_stylist in client_of_stylists:
        invited_stylists.append(client_of_stylist.stylist_id)
        client_of_stylist.client = client
        client_of_stylist.save(update_fields=['client'])
    invitations = Invitation.objects.filter(phone=user.phone)
    for invitation in invitations:
        if invitation.stylist_id not in invited_stylists:
            ClientOfStylist.objects.create(
                first_name=user.first_name,
                last_name=user.last_name,
                client=client,
                phone=user.phone,
                stylist=invitation.stylist,
            )
    return user
