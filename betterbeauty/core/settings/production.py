from typing import List

from core.constants import EnvLevel

from .defaults import *  # noqa
from .utils import get_ec2_instance_ip

LEVEL = EnvLevel.PRODUCTION

ALLOWED_HOSTS = ('*.admin.madebeauty.com', 'admin.madebeauty.com', get_ec2_instance_ip())

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
    )
}
MIDDLEWARE: List = [
    'raven.contrib.django.raven_compat.middleware.SentryResponseErrorIdMiddleware',
] + MIDDLEWARE  # noqa

INSTALLED_APPS += ['raven.contrib.django.raven_compat', ]  # noqa

# Twilio
TWILIO_SMS_ENABLED = True
TWILIO_SLACK_MOCK_ENABLED = True
TWILLIO_SLACK_CHANNEL = '#auto-twilio'

IS_GEOCODING_ENABLED = True
