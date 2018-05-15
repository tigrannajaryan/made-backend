from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path
from django.views.static import serve

from api import urls as api_urls

urlpatterns = [
    path('djangoadmin/', admin.site.urls),
    url(r'^api/', include(api_urls, namespace='api')),
]

if settings.LEVEL in ['development', 'tests']:
    urlpatterns += [
        url(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
        url(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
    ]
