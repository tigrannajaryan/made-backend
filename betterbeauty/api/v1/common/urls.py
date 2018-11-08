from django.conf.urls import url

from .views import (
    RegisterDeviceView,
    TemporaryImageUploadView,
    UnregisterDeviceView,
)

app_name = 'common'

urlpatterns = [
    url('^image/upload$', TemporaryImageUploadView.as_view(), name='temp_image_upload'),
    url('^register-device$', RegisterDeviceView.as_view(), name='register_device'),
    url('^unregister-device$', UnregisterDeviceView.as_view(), name='unregister_device'),
]
