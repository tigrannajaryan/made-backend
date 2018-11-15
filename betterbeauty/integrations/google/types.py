from core.types import StrEnum


class GoogleIntegrationType(StrEnum):
    GOOGLE_CALENDAR = 'google_calendar'


class GoogleIntegrationScope(StrEnum):
    GOOGLE_CALENDAR = 'https://www.googleapis.com/auth/calendar.events'


class GoogleIntegrationErrors(object):
    ERR_BAD_INTEGRATION_TYPE = 'err_bad_integration_type'
    ERR_FAILURE_TO_SETUP_OAUTH = 'err_failure_to_setup_oauth'
