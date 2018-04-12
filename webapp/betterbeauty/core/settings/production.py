from .defaults import *  # noqa

ALLOWED_HOSTS = ('*.admin.betterbeauty.io', 'admin.betterbeauty.io', )

DEBUG = False

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = '<set when instance is ready>'
AWS_LOCATION = 'uploads'
