from typing import List

from core.constants import EnvLevel

from .defaults import *  # noqa

from .utils import (
    get_ec2_instance_id,
    get_ec2_instance_ip_address,
    get_travis_commit_id,
)

LEVEL = EnvLevel.STAGING

AWS_INSTANCE_ID = get_ec2_instance_id()

ALLOWED_HOSTS = (
    '*.admindev.betterbeauty.io',
    'admindev.betterbeauty.io',
    '*.admindev.madebeauty.com',
    'admindev.madebeauty.com',
    get_ec2_instance_ip_address(),
)

DEBUG = False

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'elasticbeanstalk-us-east-1-024990310245'
AWS_LOCATION = 'uploads-staging'

FB_APP_ID = '1332946860139961'
FB_APP_SECRET = 'a2013eb7dc891c5534bcad9ee69bae98'

RAVEN_CONFIG = {
    'dsn': 'https://173df1e01f014501a9bed56a6998fb63:'
           'c22c5f14518a441c93cdc631f7d474df@sentry.io/1228912',
    'processors': (
        'raven.processors.SanitizePasswordsProcessor',
        'raven.processors.RemovePostDataProcessor',
    ),
    'release': get_travis_commit_id(COMMIT_ID_FILE_PATH), # noqa
    'environment': LEVEL,
    'auto_log_stacks': True,
    'attach_stacktrace': True
}

MIDDLEWARE: List = [
    'raven.contrib.django.raven_compat.middleware.SentryResponseErrorIdMiddleware',
] + MIDDLEWARE  # noqa

INSTALLED_APPS += ['raven.contrib.django.raven_compat', ]  # noqa

# Twilio
TWILIO_SMS_ENABLED = False
TWILIO_SLACK_MOCK_ENABLED = True

IS_GEOCODING_ENABLED = True
