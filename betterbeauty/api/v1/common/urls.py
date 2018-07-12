from django.conf.urls import url

from .views import (
    TemporaryImageUploadView
)

app_name = 'common'

urlpatterns = [
    url('^image/upload$', TemporaryImageUploadView.as_view(), name='temp_image_upload'),
]
