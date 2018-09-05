from .development import *  # noqa

LEVEL = 'tests'

# Twilio
TWILIO_SMS_ENABLED = False
TWILIO_SLACK_MOCK_ENABLED = False

# 0.0.0.0 must be allowed because it is used by E2E tests
ALLOWED_HOSTS = ('*', )
