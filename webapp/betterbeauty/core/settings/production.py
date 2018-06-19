from typing import List

from .defaults import *  # noqa

LEVEL = 'production'

ALLOWED_HOSTS = ('*.admin.madebeauty.com', 'admin.madebeauty.com', )

DEBUG = False

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'elasticbeanstalk-us-east-1-024990310245'
AWS_LOCATION = 'uploads-production'

FB_APP_ID = '1332946860139961'
FB_APP_SECRET = 'a2013eb7dc891c5534bcad9ee69bae98'

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
