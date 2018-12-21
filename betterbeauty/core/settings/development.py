import os
from typing import List

from core.constants import EnvLevel

from .defaults import *  # noqa
from .utils import parse_database_url

LEVEL = EnvLevel.DEVELOPMENT
BASE_URL = 'http://betterbeauty.local:8080'

PG_PORT = os.environ.get('PGPORT', 5432)

DATABASE_URL = (
    'postgis://betterbeauty:W8zSrpqUkFzReUqT@127.0.0.1:{0}/betterbeauty'.format(
        PG_PORT
    )
)

# Setup default database connection from Database URL
DATABASES = {
    'default': parse_database_url(DATABASE_URL),
}

if DJANGO_SILK_ENABLED:  # noqa
    MIDDLEWARE: List = [
        'silk.middleware.SilkyMiddleware',
    ] + MIDDLEWARE  # noqa

    INSTALLED_APPS += ['silk', ]  # noqa

DEBUG = True

FB_APP_ID = '<override in local settings>'
FB_APP_SECRET = '<override in local settings>'

# Twilio
TWILIO_SMS_ENABLED = False
TWILIO_SLACK_MOCK_ENABLED = True

IS_GEOCODING_ENABLED = False
