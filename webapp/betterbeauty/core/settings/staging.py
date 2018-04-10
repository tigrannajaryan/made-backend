from .defaults import *  # noqa

ALLOWED_HOSTS = ('*.admindev.betterbeauty.io', 'admindev.betterbeauty.io', )

DEBUG = True

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
AWS_STORAGE_BUCKET_NAME = 'betterbeauty-webapp-staging-public'
