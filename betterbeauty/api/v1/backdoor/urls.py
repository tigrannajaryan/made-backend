from django.conf.urls import url

from api.v1.backdoor.views import (
    GetAuthCodeView,
    GetUnusedPhoneNumber)

app_name = 'backdoor'

urlpatterns = [
    url('^get-auth-code', GetAuthCodeView.as_view(), name='get-auth-code'),
    url('^gen-unused-phone', GetUnusedPhoneNumber.as_view(), name='gen-unused-phone'),
]
