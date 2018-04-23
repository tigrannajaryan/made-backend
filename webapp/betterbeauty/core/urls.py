from django.contrib import admin
from django.urls import path
from django.conf.urls import include, url

from api import urls as api_urls

urlpatterns = [
    path('djangoadmin/', admin.site.urls),
    url(r'^api/', include(api_urls, namespace='api')),
]
