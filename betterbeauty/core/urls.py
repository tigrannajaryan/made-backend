from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path
from django.views.static import serve

from api import urls as api_urls
from .constants import EnvLevel
from .views import EmailUnsubscribeView, EmailVerificationView, HealthCheckView

urlpatterns = [
    path('djangoadmin/', admin.site.urls),
    url(r'^api/', include(api_urls, namespace='api')),
    url('^email/confirm$', EmailVerificationView.as_view(), name="email-verification"),
    url('^email/unsubscribe/(?P<role>(client|stylist))/(?P<uuid>[0-9a-f\-]+)$',
        EmailUnsubscribeView.as_view(), name="email-unsubscribe")

]

if settings.LEVEL in [EnvLevel.DEVELOPMENT, EnvLevel.TESTS]:
    urlpatterns += [
        url(r'^media/(?P<path>.*)$', serve, {
            'document_root': settings.MEDIA_ROOT,
        }),
        url(r'^static/(?P<path>.*)$', serve, {
            'document_root': settings.STATIC_ROOT,
        }),
    ]

if settings.DJANGO_SILK_ENABLED:
    urlpatterns += [url(r'^silk/', include('silk.urls', namespace='silk'))]

if settings.LEVEL in [EnvLevel.PRODUCTION, EnvLevel.STAGING]:
    urlpatterns += [
        url(r'^healthcheck', HealthCheckView.as_view()),
    ]
