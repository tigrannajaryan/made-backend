from django.conf.urls import url

from .views import (
    CustomObtainJWTToken,
    CustomRefreshJSONWebToken,
    FBRegisterLoginView,
    RegisterUserView,
    SendCodeView,
    VerifyCodeView,
)

app_name = 'auth'

urlpatterns = [
    url(r'^get-token$', CustomObtainJWTToken.as_view(), name='get_jwt_token'),
    url(r'^refresh-token$', CustomRefreshJSONWebToken.as_view(), name='refresh_jwt_token'),
    url(r'^register$', RegisterUserView.as_view(), name='register'),
    url(r'^get-token-fb$', FBRegisterLoginView.as_view(), name='get_fb_token'),
    url(r'^get-code$', SendCodeView.as_view(), name='send-code'),
    url(r'^code/confirm$', VerifyCodeView.as_view(), name='verify-code'),
]
