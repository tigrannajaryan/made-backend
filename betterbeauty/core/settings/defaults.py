import datetime
import os

from path import Path

from core.constants import EnvVars
from core.settings.utils import get_file_handler_dict, get_logger_dict
from integrations.push.types import MobileAppIdType

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
PATH = Path(__file__).parent
ROOT_PATH = PATH.parent.parent
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# a file on AWS instance that contains string with commit id representing
# current release

COMMIT_ID_FILE_PATH = Path(ROOT_PATH.parent / 'meta' / 'commit_id.txt')


LOGS_PATH = ROOT_PATH
LOG_MAX_FILESIZE = 10485760

LOGGING = {
    'version': 1,
    'formatters': {
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '%(levelname)s %(asctime)s %(message)s',
        },
        'simple': {
            'level': 'DEBUG',
            'format': '%(levelname)s %(asctime)s %(message)s',
        },
        'verbose': {
            'format': ('%(levelname)s %(asctime)s %(name)s in .%(funcName)s '
                       '(line %(lineno)d): %(message)s'),
        }
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'sentry': {
            'filters': ['require_debug_false', ],
            'formatter': 'verbose',
            'level': 'ERROR',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true', ],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        },
        'console_simple': {
            'level': 'DEBUG',
            'filters': ['require_debug_true', ],
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'syslog': {
            'filters': ['require_debug_false', ],
            'level': 'DEBUG',
            'class': 'logging.handlers.SysLogHandler',
            'facility': 'local7',
            'address': '/dev/log',
            'formatter': 'verbose'
        },
        'null': {
            'class': 'logging.NullHandler',
        },
        'django_log_file': get_file_handler_dict(LOGS_PATH, 'django', 'django.server', ),
        'madebeauty_log_file': get_file_handler_dict(LOGS_PATH, 'madebeauty', 'django.server', ),
    },
    'loggers': {
        'django': get_logger_dict(
            ['sentry', 'console_simple', 'syslog', 'django_log_file', ], 'INFO'),
        'django.server': get_logger_dict(
            ['sentry', 'console_simple', 'syslog', 'django_log_file', ], 'INFO'),
        'django.request': get_logger_dict(
            ['sentry', 'console_simple', 'syslog', 'django_log_file', ], 'INFO'),
        'django.security.DisallowedHost': get_logger_dict(
            ['null', ]),
        'api': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'appointment': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'billing': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'client': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'core': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'integrations': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'notifications': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'pricing': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'salon': get_logger_dict(
            ['sentry', 'console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'auto_checkout': get_logger_dict(
            ['syslog', 'sentry', ], 'INFO'
        ),
    }
}

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(EnvVars.SECRET_KEY,
                            "%3h%_#mrt&eb+k-auzt(qdg_ix&9x!h_shf%bk=kr@a_cg__j_")

ALLOWED_HOSTS = ['betterbeauty.local', ]

DATABASE_URL = ''

if EnvVars.RDS_DB_NAME in os.environ:
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': os.environ[EnvVars.RDS_DB_NAME],
            'USER': os.environ[EnvVars.RDS_USERNAME],
            'PASSWORD': os.environ[EnvVars.RDS_PASSWORD],
            'HOST': os.environ[EnvVars.RDS_HOSTNAME],
            'PORT': os.environ[EnvVars.RDS_PORT],
        }
    }

READ_ONLY_USER_PASSWORD = os.environ.get(
    EnvVars.READ_ONLY_USER_PASSWORD, None)

# Application definition

INSTALLED_APPS = [
    # django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.gis',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'corsheaders',
    'custom_user',
    'django_extensions',
    'push_notifications',
    'rest_framework',
    'storages',

    # Internal apps
    'api',
    'billing',
    'appointment',
    'client',
    'core',
    'integrations',
    'notifications',
    'salon',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'core.exceptions.middleware.ExceptionToHTTPStatusCodeMiddleware'
]

ROOT_URLCONF = 'core.urls'
APPEND_SLASH = False

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/2.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_jwt.authentication.JSONWebTokenAuthentication',
    ),
    'EXCEPTION_HANDLER':
        'api.common.handlers.formatted_exception_handler',
}

AUTH_USER_MODEL = 'core.User'

JWT_AUTH = {
    'JWT_ALLOW_REFRESH': True,
    'JWT_AUTH_HEADER_PREFIX': 'Token',  # add header Authentication: Token <jwt_token>
    'JWT_EXPIRATION_DELTA': datetime.timedelta(days=30),  # set expiration for 1 month
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=30),  # set refresh expiry for 1 month
    'JWT_RESPONSE_PAYLOAD_HANDLER': 'core.utils.auth.jwt_response_payload_handler',
}

# as long as we employ JWT based auth - we can safely enable CORS requests from anywhere
CORS_ORIGIN_ALLOW_ALL = True

# Internationalization

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files settings
MEDIA_ROOT = (ROOT_PATH / 'media')
MEDIA_URL = '/media/'
STATIC_ROOT = (ROOT_PATH / 'static')
STATIC_URL = '/static/'

MAX_FILE_UPLOAD_SIZE = 1024 * 1024 * 5  # 5MB

AWS_S3_FILE_OVERWRITE = False
# On production file with this name will be created during healthcheck
# to verify that an instance has write access
AWS_S3_WRITE_ACCESS_TEST_FILE_NAME = 'write-access-test.tmp'

# We will test only ~5% of all healthchecks against real write operation
# to save on S3 PUT calls, making a real PUT operation once every 20
# healthcheck attempts
AWS_S3_WRITE_ACCESS_TEST_PERIODICITY = 20

DEBUG = False

CATCH_ALL_EXCEPTIONS = False

TWILIO_SMS_ENABLED = False
TWILIO_SLACK_MOCK_ENABLED = False
TWILIO_FROM_TEL = '+13477516233'

GOOGLE_AUTOCOMPLETE_API_KEY = os.environ.get(
    EnvVars.GOOGLE_AUTOCOMPLETE_API_KEY, '<override in local.py>')

GOOGLE_GEOCODING_API_KEY = os.environ.get(
    EnvVars.GOOGLE_GEOCODING_API_KEY, '<override in local.py>')

IPSTACK_API_KEY = os.environ.get(
    EnvVars.IPSTACK_API_KEY, '<override in local.py>')

DJANGO_SILK_ENABLED = False

IS_SLACK_ENABLED = True

# slack channels
TWILLIO_SLACK_CHANNEL = '#auto-twilio-dev'
AUTO_SIGNUP_SLACK_CHANNEL = '#auto-signup-dev'
AUTO_BOOKING_SLACK_CHANNEL = '#auto-booking-dev'
AUTO_EMAIL_SLACK_CHANNEL = '#auto-email-dev'
AUTO_STRIPE_SLACK_CHANNEL = '#auto-stripe-dev'

# slack hooks
TWILLIO_SLACK_HOOK = (
    'https://hooks.slack.com/services/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'
)
AUTO_SIGNUP_SLACK_HOOK = (
    'https://hooks.slack.com/services/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'
)
AUTO_BOOKING_SLACK_HOOK = (
    'https://hooks.slack.com/services/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'
)
AUTO_EMAIL_SLACK_HOOK = (
    'https://hooks.slack.com/services/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'
)
AUTO_STRIPE_SLACK_HOOK = (
    'https://hooks.slack.com/services/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'
)

#  notifications
NOTIFICATIONS_ENABLED = True

IOS_PUSH_CERTIFICATES_PATH = Path(ROOT_PATH.parent / 'push_certificates')

PUSH_NOTIFICATIONS_SETTINGS = {
    'CONFIG': 'push_notifications.conf.AppConfig',
    'APPLICATIONS': {
        # TODO: verify topic settings
        MobileAppIdType.ANDROID_CLIENT.value: {
            'PLATFORM': 'FCM',
            'API_KEY': os.environ.get(EnvVars.FCM_SERVER_KEY, ''),
        },
        MobileAppIdType.ANDROID_STYLIST.value: {
            'PLATFORM': 'FCM',
            'API_KEY': os.environ.get(EnvVars.FCM_SERVER_KEY, ''),
        },
        # certificate settings for iOS apps built locally,
        # with development certificate
        MobileAppIdType.IOS_STYLIST_DEV.value: {
            'PLATFORM': 'APNS',
            'CERTIFICATE': Path(IOS_PUSH_CERTIFICATES_PATH / 'local-stylist-staging.pem'),
            'USE_SANDBOX': True,
            'TOPIC': 'com.madebeauty.stylist.beta',
        },
        MobileAppIdType.IOS_CLIENT_DEV.value: {
            'PLATFORM': 'APNS',
            'CERTIFICATE': Path(IOS_PUSH_CERTIFICATES_PATH / 'local-client-staging.pem'),
            'USE_SANDBOX': True,
            'TOPIC': 'com.madebeauty.client.staging',
        },
    }
}

GOOGLE_OAUTH_CREDENTIALS_FILE_PATH = '<override in local.py>'
# enable synchronization of Appointments with Stylist calendars
GOOGLE_CALENDAR_STYLIST_SYNC_ENABLED = True
GOOGLE_CALENDAR_CLIENT_SYNC_ENABLED = True

MINUTES_BEFORE_REQUESTING_NEW_CODE = 0

STRIPE_PUBLISHABLE_KEY = os.environ.get(EnvVars.STRIPE_PUBLISHABLE_KEY, '<override in local.py')
STRIPE_SECRET_KEY = os.environ.get(EnvVars.STRIPE_SECRET_KEY, '<override in local.py')
STRIPE_CONNECT_CLIENT_ID = os.environ.get(
    EnvVars.STRIPE_CONNECT_CLIENT_ID, '<override in local.py'
)
# this is what will show in the client's bank statement as the merchant name for a charge
STRIPE_DEFAULT_PAYMENT_DESCRIPTOR = 'MadeBeauty, Inc'
STRIPE_DEFAULT_CURRENCY = 'usd'
