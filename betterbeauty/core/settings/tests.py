from core.constants import EnvLevel  # noqa

from .development import *  # noqa

LEVEL = EnvLevel.TESTS

# Twilio
TWILIO_SMS_ENABLED = False
TWILIO_SLACK_MOCK_ENABLED = False

# 0.0.0.0 must be allowed because it is used by E2E tests
ALLOWED_HOSTS = ('*', )

IS_SLACK_ENABLED = False
PUSH_NOTIFICATIONS_ENABLED = False
