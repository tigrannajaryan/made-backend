from uuid import uuid4

from client.models import Client
from core.models import User
from core.types import UserRole


def create_client_profile_for_user(user: User, **kwargs) -> Client:
    return Client.objects.create(user=user, **kwargs)


def create_nonlogin_client(first_name: str, last_name: str, phone: str) -> Client:
    """Return Client with non-loggable user account with auto-generated email"""

    bogus_email = 'client-{0}@madebeauty.com'.format(uuid4())
    user = User.objects.create_user(
        email=bogus_email,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        is_active=False,
        role=UserRole.CLIENT
    )
    user.set_unusable_password()
    client = create_client_profile_for_user(user)
    return client
