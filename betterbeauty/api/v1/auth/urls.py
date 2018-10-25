from django.conf.urls import url

from .views import (
    CustomRefreshJSONWebToken,
    SendCodeView,
    VerifyCodeView,
)

app_name = 'auth'

urlpatterns = [
    url(r'^refresh-token$', CustomRefreshJSONWebToken.as_view(), name='refresh_jwt_token'),
    url(r'^get-code$', SendCodeView.as_view(), name='send-code'),
    url(r'^code/confirm$', VerifyCodeView.as_view(), name='verify-code'),
]
