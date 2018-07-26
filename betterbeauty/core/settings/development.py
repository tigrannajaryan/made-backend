import os
from .defaults import *  # noqa
from .utils import parse_database_url

LEVEL = 'development'

PG_PORT = os.environ.get('PGPORT', 5432)

DATABASE_URL = (
    'postgres://betterbeauty:W8zSrpqUkFzReUqT@127.0.0.1:{0}/betterbeauty'.format(
        PG_PORT
    )
)

# Setup default database connection from Database URL
DATABASES = {
    'default': parse_database_url(DATABASE_URL),
}

DEBUG = True

FB_APP_ID = '<override in local settings>'
FB_APP_SECRET = '<override in local settings>'

# Twilio
TWILIO_SMS_ENABLED = False
TWILIO_SLACK_MOCK_ENABLED = True
