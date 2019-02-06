"""
Slack email backend that does sends the message to slack.
"""

from django.core.mail.backends.base import BaseEmailBackend

from integrations.slack import send_slack_email


class EmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        for message in email_messages:
            send_slack_email(message)
        return len(list(email_messages))
