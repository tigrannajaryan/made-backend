import logging
from typing import Iterable

from django.conf import settings
from django.utils import timezone

from oauth2client import client

from core.models import User, UserRole


from .types import GoogleIntegrationScope

logger = logging.getLogger(__name__)


def get_oauth_credentials_from_server_code(
        auth_code: str, scope: Iterable[str]
) -> client.OAuth2Credentials:
    """
    Return OAuth2Credentials in exchange for server auth code issued for particular
    google web application
    :param auth_code: Auth code obtained on the frontend
    :param scope: iterable of strings or string containing required scope; see scope list
    at https://developers.google.com/identity/protocols/googlescopes
    :return: oauth2client.client.OAuth2Credentials objects
    """

    # In order for this code to work as expected, redirect_uri of "http://localhost" must
    # be configured in client credentials section in Google developer console
    # https://console.developers.google.com/apis/credentials?
    # project=made-staging&organizationId=1065847735654
    credentials: client.OAuth2Credentials = client.credentials_from_clientsecrets_and_code(
        filename=settings.GOOGLE_OAUTH_CREDENTIALS_FILE_PATH,
        scope=scope,
        code=auth_code,
        redirect_uri='http://localhost'
    )
    return credentials


def add_google_integration_for_user(
        user: User, user_role: UserRole, auth_code: str, scope: Iterable[str]
):
    """
    Retrieves access/refresh tokens from Google API in exchange for given auth_code, and
    saves resulting credentials to stylist or client objects of given user
    :param user: core.User
    :param user_role: client or stylist, where to save
    :param auth_code: Auth code obtained on the frontend
    :param scope: iterable of strings or string containing required scope; see scope list
    at https://developers.google.com/identity/protocols/googlescopes
    """
    assert user_role in user.role
    object_to_save = {
        UserRole.CLIENT: getattr(user, 'client', None),
        UserRole.STYLIST: getattr(user, 'stylist', None),
    }[user_role]
    assert object_to_save

    credentials: client.OAuth2Credentials = get_oauth_credentials_from_server_code(
        auth_code=auth_code, scope=scope
    )
    object_to_save.google_access_token = credentials.access_token
    object_to_save.google_refresh_token = credentials.refresh_token
    object_to_save.google_integration_added_at = timezone.now()

    object_to_save.save(
        update_fields=[
            'google_access_token', 'google_refresh_token', 'google_integration_added_at'
        ]
    )


def add_google_calendar_integration_for_user(
        user: User, user_role: UserRole, auth_code: str
):
    """
    Retrieves access/refresh tokens from Google API in exchange for given auth_code, and
    saves resulting credentials to stylist or client objects of given user
    :param user: core.User
    :param user_role: client or stylist, where to save
    :param auth_code: Auth code obtained on the frontend
    at https://developers.google.com/identity/protocols/googlescopes
    """

    return add_google_integration_for_user(
        user=user, user_role=user_role, auth_code=auth_code,
        scope=[GoogleIntegrationScope.GOOGLE_CALENDAR.value, ]
    )
