from typing import List

from core.constants import EnvLevel

from .defaults import *  # noqa
from .utils import (
    get_ec2_instance_id,
    get_ec2_instance_ip_address,
    get_travis_commit_id,
)

LEVEL = EnvLevel.PRODUCTION

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
TWILIO_SLACK_MOCK_ENABLED = True

IS_GEOCODING_ENABLED = True

# slack channels
TWILLIO_SLACK_CHANNEL = '#auto-twilio'
AUTO_SIGNUP_SLACK_CHANNEL = '#auto-signup'
