from .defaults import *  # noqa

ALLOWED_HOSTS = ('*.admin.betterbeauty.io', 'admin.betterbeauty.io', )

DEBUG = False

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto.S3BotoStorage'
AWS_STORAGE_BUCKET_NAME = 'betterbeauty-webapp-production-public'
