from client.models import Client
from core.models import User


def create_client_profile_for_user(user: User, **kwargs) -> Client:
    return Client.objects.create(user=user, **kwargs)
