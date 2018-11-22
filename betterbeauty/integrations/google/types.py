from typing import Optional

from core.types import NamedTuple, StrEnum


class GoogleIntegrationType(StrEnum):
    GOOGLE_CALENDAR = 'google_calendar'


class GoogleIntegrationScope(StrEnum):
    GOOGLE_CALENDAR = 'https://www.googleapis.com/auth/calendar.events'


class GoogleIntegrationErrors(object):
    ERR_BAD_INTEGRATION_TYPE = 'err_bad_integration_type'
    ERR_FAILURE_TO_SETUP_OAUTH = 'err_failure_to_setup_oauth'


class GoogleCalendarAttendee(NamedTuple):
    display_name: str
    email: Optional[str] = None
