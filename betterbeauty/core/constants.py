from .types import StrEnum


class EnvLevel(StrEnum):
    PRODUCTION = 'production'
    STAGING = 'staging'
    DEVELOPMENT = 'development'
    TESTS = 'tests'


class EnvVars(StrEnum):

    RDS_DB_NAME = 'RDS_DB_NAME'
    RDS_USERNAME = 'RDS_USERNAME'
    RDS_PASSWORD = 'RDS_PASSWORD'
    RDS_HOSTNAME = 'RDS_HOSTNAME'
    RDS_PORT = 'RDS_PORT'
    READ_ONLY_USER_PASSWORD = 'READ_ONLY_USER_PASSWORD'
    GOOGLE_AUTOCOMPLETE_API_KEY = 'GOOGLE_AUTOCOMPLETE_API_KEY'
    GOOGLE_GEOCODING_API_KEY = 'GOOGLE_GEOCODING_API_KEY'
    IPSTACK_API_KEY = 'IPSTACK_API_KEY'
    FCM_SERVER_KEY = 'FCM_SERVER_KEY'
    LEVEL = 'LEVEL'
    PGPORT = 'PGPORT'


DEFAULT_TAX_RATE = 0.045

DEFAULT_CARD_FEE = 0.0275

DEFAULT_FIRST_TIME_BOOK_DISCOUNT_PERCENT = 0
DEFAULT_REBOOK_WITHIN_1_WEEK_DISCOUNT_PERCENT = 25
DEFAULT_REBOOK_WITHIN_2_WEEKS_DISCOUNT_PERCENT = 20
DEFAULT_REBOOK_WITHIN_3_WEEKS_DISCOUNT_PERCENT = 15
DEFAULT_REBOOK_WITHIN_4_WEEKS_DISCOUNT_PERCENT = 10

DEFAULT_WEEKDAY_DISCOUNT_PERCENTS = {
    1: 20,
    2: 20,
    3: 20,
    4: 20,
    5: 0,
    6: 0,
    7: 0
}

# We restrict some environment vars to specific environments.
# For eg. twilio is restricted only to production.
# ENV_BLACKLIST contains the map of blacklisted vars for each envs.
ENV_BLACKLIST = {
    EnvLevel.PRODUCTION: [
        'BACKDOOR_API_KEY',
    ],
    EnvLevel.STAGING: [
        'TWILIO_ACCOUNT_SID',
        'TWILIO_AUTH_TOKEN'
    ]
}


EMAIL_VERIFICATION_SUCCESS_REDIRECT_URL = 'https://madebeauty.com/email-confirm-success/'
EMAIL_VERIFICATION_FAILIURE_REDIRECT_URL = 'https://madebeauty.com/email-confirm-expired/'
