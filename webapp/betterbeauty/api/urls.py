from django.conf.urls import include, url

from .v1 import urls as v1_urls

app_name = 'api'

urlpatterns = [
    url('^v1/', include(v1_urls, namespace='v1')),
]
