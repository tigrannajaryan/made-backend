import datetime
import os

from path import Path

from core.settings.utils import get_file_handler_dict, get_logger_dict

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
PATH = Path(__file__).parent
ROOT_PATH = PATH.parent.parent
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
        'django_log_file': get_file_handler_dict(LOGS_PATH, 'django', 'django.server', ),
        'madebeauty_log_file': get_file_handler_dict(LOGS_PATH, 'madebeauty', 'django.server', ),
    },
    'loggers': {
        'django': get_logger_dict(['console_simple', 'syslog', 'django_log_file', ], 'INFO'),
        'django.server': get_logger_dict(
            ['console_simple', 'syslog', 'django_log_file', ], 'INFO'
        ),
        'django.request': get_logger_dict(
            ['console_simple', 'syslog', 'django_log_file', ], 'INFO'),
        'api': get_logger_dict(['console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'appointment': get_logger_dict(['console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'client': get_logger_dict(['console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'core': get_logger_dict(['console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'integrations': get_logger_dict(['console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'pricing': get_logger_dict(['console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
        'salon': get_logger_dict(['console', 'syslog', 'madebeauty_log_file', ], 'DEBUG'),
    }
}

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '_8aa&jg@cd64@%2%20&6kzpu$cf8xu3hme&q&fu2gei(#7*h0r'

ALLOWED_HOSTS = ['betterbeauty.local', ]

DATABASE_URL = ''

if 'RDS_DB_NAME' in os.environ:
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': os.environ['RDS_DB_NAME'],
            'USER': os.environ['RDS_USERNAME'],
            'PASSWORD': os.environ['RDS_PASSWORD'],
            'HOST': os.environ['RDS_HOSTNAME'],
            'PORT': os.environ['RDS_PORT'],
        }
    }


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
    'rest_framework',
    'storages',

    # Internal apps
    'api',
    'appointment',
    'client',
    'core',
    'integrations',
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

    'core.exceptions.middleware.ExceptionToHTTPStatusCodeMIddleware'
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

DEBUG = False

CATCH_ALL_EXCEPTIONS = False

# Twilio
TWILLIO_SLACK_HOOK = (
    'https://hooks.slack.com/services/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'
)
TWILIO_SMS_ENABLED = False
TWILIO_SLACK_MOCK_ENABLED = False
TWILIO_FROM_TEL = '+13477516233'
TWILLIO_SLACK_CHANNEL = '#auto-twilio-dev'

GOOGLE_AUTOCOMPLETE_API_KEY = os.environ.get(
    'GOOGLE_AUTOCOMPLETE_API_KEY', '<override in local.py>')

GOOGLE_GEOCODING_API_KEY = os.environ.get(
    'GOOGLE_GEOCODING_API_KEY', '<override in local.py>')

IPSTACK_API_KEY = os.environ.get(
    'IPSTACK_API_KEY', '<override in local.py>')
