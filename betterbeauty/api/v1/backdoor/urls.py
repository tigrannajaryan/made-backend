from django.conf.urls import url

from api.v1.backdoor.views import (
    GetAuthCodeView,
)

app_name = 'backdoor'

urlpatterns = [
    url('^get-auth-code', GetAuthCodeView.as_view(), name='get-auth-code'),
]
