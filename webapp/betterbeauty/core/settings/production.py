from .defaults import *  # noqa

LEVEL = 'production'

ALLOWED_HOSTS = ('*.admin.betterbeauty.io', 'admin.betterbeauty.io', )

DEBUG = False

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = '<set when instance is ready>'
AWS_LOCATION = 'uploads'

# TODO: add FB settings
FB_APP_ID = ''
FB_APP_SECRET = ''
