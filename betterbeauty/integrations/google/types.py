from typing import Optional

from core.types import NamedTuple, StrEnum


class IntegrationType(StrEnum):
    GOOGLE_CALENDAR = 'google_calendar'
    STRIPE_CONNECT = 'stripe_connect'


class GoogleIntegrationScope(StrEnum):
    GOOGLE_CALENDAR = 'https://www.googleapis.com/auth/calendar.events'


class IntegrationErrors(object):
    ERR_BAD_INTEGRATION_TYPE = 'err_bad_integration_type'
    ERR_FAILURE_TO_SETUP_OAUTH = 'err_failure_to_setup_oauth'
    ERR_SERVER_FAILURE = 'err_server_failure'


class GoogleCalendarAttendee(NamedTuple):
    display_name: str
    email: Optional[str] = None
