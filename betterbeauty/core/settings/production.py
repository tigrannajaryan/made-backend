from typing import List

from core.constants import EnvLevel
from .defaults import *  # noqa
from .defaults import (
    IOS_PUSH_CERTIFICATES_PATH,
    MobileAppIdType,
    Path,
    PUSH_NOTIFICATIONS_SETTINGS,
    ROOT_PATH,
)
from .utils import (
    get_ec2_instance_id,
    get_ec2_instance_ip_address,
    get_travis_commit_id,
)

LEVEL = EnvLevel.PRODUCTION
BASE_URL = 'https://admin.madebeauty.com'

AWS_INSTANCE_ID = get_ec2_instance_id()
ALLOWED_HOSTS = ('*.admin.madebeauty.com', 'admin.madebeauty.com', get_ec2_instance_ip_address())

DEBUG = False

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'elasticbeanstalk-us-east-1-024990310245'
AWS_LOCATION = 'uploads-production'

FB_APP_ID = '877860949068191'
FB_APP_SECRET = '013426e3d984676a892e9f60d1b8cab2'

RAVEN_CONFIG = {
    'dsn': 'https://97056d677705432898803866b8f649f0:'
           '5ed4479c64f14750925ef4ab389557ef@sentry.io/1228913',
    'processors': (
        'raven.processors.SanitizePasswordsProcessor',
        'raven.processors.RemovePostDataProcessor',
    ),
    'release': get_travis_commit_id(COMMIT_ID_FILE_PATH), # noqa
    'environment': LEVEL,
}
MIDDLEWARE: List = [
    'raven.contrib.django.raven_compat.middleware.SentryResponseErrorIdMiddleware',
] + MIDDLEWARE  # noqa

INSTALLED_APPS += ['raven.contrib.django.raven_compat', ]  # noqa

# Twilio
TWILIO_SMS_ENABLED = True
TWILIO_SLACK_MOCK_ENABLED = False

IS_GEOCODING_ENABLED = True

# slack channels
TWILLIO_SLACK_CHANNEL = '#auto-twilio'
AUTO_SIGNUP_SLACK_CHANNEL = '#auto-signup'
AUTO_BOOKING_SLACK_CHANNEL = '#auto-booking'

NOTIFICATIONS_ENABLED = True

PUSH_NOTIFICATIONS_SETTINGS['APPLICATIONS'].update({  # type: ignore
    # certificate settings for iOS apps built with distribution certificate,
    # e.g. those from TestFlight or AppStore
    MobileAppIdType.IOS_STYLIST.value: {
        'PLATFORM': 'APNS',
        'CERTIFICATE': Path(IOS_PUSH_CERTIFICATES_PATH / 'server-stylist-production.pem'),
        'TOPIC': 'com.madebeauty.stylist.production',
    },
    MobileAppIdType.IOS_CLIENT.value: {
        'PLATFORM': 'APNS',
        'CERTIFICATE': Path(IOS_PUSH_CERTIFICATES_PATH / 'server-client-production.pem'),
        'TOPIC': 'com.madebeauty.client.production',
    },
})

GOOGLE_CALENDAR_STYLIST_SYNC_ENABLED = True
GOOGLE_CALENDAR_CLIENT_SYNC_ENABLED = True
GOOGLE_OAUTH_CREDENTIALS_FILE_PATH = Path(
    ROOT_PATH.parent / 'google_credentials' / 'webclient-production.json')

MINUTES_BEFORE_REQUESTING_NEW_CODE = 2
