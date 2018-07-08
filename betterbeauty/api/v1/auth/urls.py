from django.conf.urls import url

from rest_framework_jwt.views import obtain_jwt_token, refresh_jwt_token

from .views import FBRegisterLoginView, RegisterUserView, SendCodeView, VerifyCodeView

app_name = 'auth'

urlpatterns = [
    url(r'^get-token$', obtain_jwt_token, name='get_jwt_token'),
    url(r'^refresh-token$', refresh_jwt_token, name='refresh_jwt_token'),
    url(r'^register$', RegisterUserView.as_view(), name='register'),
    url(r'^get-token-fb$', FBRegisterLoginView.as_view(), name='get_fb_token'),
    url(r'^send-code', SendCodeView.as_view(), name='send-code'),
    url(r'^verify-code', VerifyCodeView.as_view(), name='verify-code'),
]
