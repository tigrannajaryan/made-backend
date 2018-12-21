from django.conf.urls import url

from integrations.twilio.webhooks import handle_sms_reply, update_sms_status

app_name = 'webhooks'

urlpatterns = [
    url('^twilio/update-sms-status', update_sms_status, name='update-sms-status'),
    url('^twilio/handle-sms-reply', handle_sms_reply, name='handle-sms-reply'),
]
