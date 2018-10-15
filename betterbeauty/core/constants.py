from .types import StrEnum


class EnvLevel(StrEnum):
    PRODUCTION = 'production'
    STAGING = 'staging'
    DEVELOPMENT = 'development'
    TESTS = 'tests'


DEFAULT_TAX_RATE = 0.065

DEFAULT_CARD_FEE = 0.0275

DEFAULT_FIRST_TIME_BOOK_DISCOUNT_PERCENT = 10
DEFAULT_REBOOK_WITHIN_1_WEEK_DISCOUNT_PERCENT = 25
DEFAULT_REBOOK_WITHIN_2_WEEKS_DISCOUNT_PERCENT = 20
DEFAULT_REBOOK_WITHIN_3_WEEKS_DISCOUNT_PERCENT = 15
DEFAULT_REBOOK_WITHIN_4_WEEKS_DISCOUNT_PERCENT = 10
DEFAULT_REBOOK_WITHIN_5_WEEKS_DISCOUNT_PERCENT = 5
DEFAULT_REBOOK_WITHIN_6_WEEKS_DISCOUNT_PERCENT = 0

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
