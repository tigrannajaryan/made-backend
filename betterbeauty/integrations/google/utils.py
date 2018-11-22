import datetime
import json
import logging
import os.path
from typing import Any, Dict, Iterable, Optional

import pytz
from django.conf import settings
from django.db.models import Model
from django.utils import timezone

from googleapiclient.discovery import build, HttpError, Resource
from httplib2 import Http
from oauth2client import client

from core.models import User, UserRole


from .types import GoogleCalendarAttendee, GoogleIntegrationScope

logger = logging.getLogger(__name__)

GoogleAuthException = HttpError

GOOGLE_JSON_CREDENTIALS: Optional[client.OAuth2Credentials] = None

# persistently load credentials from file
if os.path.isfile(settings.GOOGLE_OAUTH_CREDENTIALS_FILE_PATH):
    with open(settings.GOOGLE_OAUTH_CREDENTIALS_FILE_PATH, 'r') as json_credentials_file:
        GOOGLE_JSON_CREDENTIALS = json.load(json_credentials_file)


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


def build_oauth_credentials_from_tokens(
        access_token: str, refresh_token: str,
) -> Optional[client.OAuth2Credentials]:
    """
    Builds OAuth credentials from access/refresh token

    :param access_token: string representing access token
    :param refresh_token: string representing refresh token
    :return: OAuth2Credentials object
    """
    json_credentials = GOOGLE_JSON_CREDENTIALS
    if not json_credentials:
        return None
    credentials: client.OAuth2Credentials = client.OAuth2Credentials(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=json_credentials['web']['client_id'],
        client_secret=json_credentials['web']['client_secret'],
        token_expiry=None,
        token_uri=json_credentials['web']['token_uri'],
        user_agent=None,
    )
    return credentials


def update_model_with_token_from_http_request(
        http_object: Http, model_object_to_update: Optional[Model]=None,
        field_to_update: Optional[str]=None
):
    """Extract access token from pre-authorized request and send it to the model object"""
    if hasattr(http_object, 'request'):
        if http_object.request.credentials:
            if model_object_to_update and field_to_update:
                setattr(
                    model_object_to_update, field_to_update,
                    http_object.request.credentials.access_token
                )
                model_object_to_update.save(update_fields=[field_to_update, ])


def build_oauth_http_object_from_tokens(
        access_token: str, refresh_token: str,
        model_object_to_update: Optional[Model]=None,
        access_token_field: Optional[str]=None
) -> Optional[Http]:
    """
    Builds and authorizes OAuth credentials from access/refresh token,
    and update access token if necessary. Return Http resource capable of making
    requests to Google API services

    :param access_token: string representing access token
    :param refresh_token: string representing refresh token
    :param model_object_to_update: optional model object to refresh access token
    :param access_token_field: name of field to write updated access token
    :return: Http object containing OAuth2Credentials objects if auth successful,
    None otherwise
    """
    credentials: Optional[client.OAuth2Credentials] = build_oauth_credentials_from_tokens(
        access_token=access_token, refresh_token=refresh_token
    )
    if not credentials:
        return None
    http_object: Http = credentials.authorize(Http())
    update_model_with_token_from_http_request(
        http_object, model_object_to_update, access_token_field
    )

    return http_object


def build_google_calendar_events_service_resource(oauth_http_object: Http) -> Resource:
    """
    Return lazy Resource object for Google Calendar Events API, pre-initialized with
    Http request containing credentials
    :param oauth_http_object:
    :return:
    """
    calendar_service: Resource = build('calendar', 'v3', http=oauth_http_object)
    return calendar_service.events()


def build_google_calendar_body(
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        summary: str,
        attendees: Iterable[GoogleCalendarAttendee],
        description: Optional[str]=None,
        location: Optional[str]=None
) -> Dict[str, Any]:
    """
    Build dict representing body of google calendar event. See
    https://developers.google.com/resources/api-libraries/documentation/
    calendar/v3/python/latest/calendar_v3.events.html for complete list of
    available fields

    :param start_at: tz-aware time of start
    :param end_at: tz-aware time of end
    :param attendees: list of attendees
    :param summary: Title of the event (how it is displayed in the summary view)
    :param description: Event notes
    :param location: location of the event in the free form. Can be name of place, address, etc.
    :return:
    """
    assert start_at.tzinfo, 'Start time must be tz-aware'
    assert end_at.tzinfo, 'End time must be tz-aware'

    # TODO: uncomment lines below when we want to add attendees. We'll
    # TODO: need to find a smart way of getting the list
    # attendees_of_event = [{
    #     'displayName': attendee.display_name,
    #     'email': attendee.email,
    #     'responseStatus': 'accepted'
    # } for attendee in attendees if attendee.email]
    event_body = {
        'attachments': [],
        'summary': summary,
        'description': description,
        'location': location,
        'start': {
            'dateTime': start_at.astimezone(pytz.utc).isoformat()
        },
        'end': {
            'dateTime': end_at.astimezone(pytz.utc).isoformat()
        },
        'attendees': [],
        'conferenceData': None
    }
    return event_body


def create_calendar_event(
        oauth_http_object: Http,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
        attendees: Iterable[GoogleCalendarAttendee],
        summary: Optional[str]=None,
        description: Optional[str]=None,
        location: Optional[str]=None,
) -> Optional[str]:
    """
    Create a calendar entry in the primary calendar of a user identified with auth_credentials
    :param oauth_http_object: Pre-authorized Http object
    :param start_at: tz-aware time of start
    :param end_at: tz-aware time of end
    :param attendees: list of attendees
    :param summary: Title of the event (how it is displayed in the summary view)
    :param description: Event notes
    :param location: location of the event in the free form. Can be name of place, address, etc.
    :return: string representing event id, or None if unsuccessful
    """
    event_body = build_google_calendar_body(
        start_at=start_at, end_at=end_at, summary=summary, attendees=attendees,
        description=description, location=location
    )
    calendar_service = build_google_calendar_events_service_resource(oauth_http_object)
    calendar_event = calendar_service.insert(
        calendarId='primary',
        body=event_body,
        conferenceDataVersion=1
    ).execute()
    if calendar_event and 'id' in calendar_event:
        return calendar_event['id']
    return None


def cancel_calendar_event(oauth_http_object: Http, event_id: str) -> Optional[str]:
    """
    Cancels event in user's google calendar by patching it and setting status
    to 'cancelled'
    :param oauth_http_object: oauth_http_object: Pre-authorized Http object
    :param event_id: id of event to cancel
    :return: event_id of cancelled event, or None if unsuccessful
    """
    calendar_service = build_google_calendar_events_service_resource(oauth_http_object)
    calendar_event = calendar_service.patch(
        calendarId='primary',
        eventId=event_id,
        body={
            'status': 'cancelled'
        }
    ).execute()
    if calendar_event and 'id' in calendar_event:
        return calendar_event['id']
    return None
