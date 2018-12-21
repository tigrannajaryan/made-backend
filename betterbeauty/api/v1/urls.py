from django.conf.urls import include, url

from .auth import urls as auth_urls
from .backdoor import urls as backdoor_urls
from .client import urls as client_urls
from .common import urls as common_urls
from .stylist import urls as stylist_urls
from .webhooks import urls as webhooks_urls

app_name = 'v1'

urlpatterns = [
    url('^auth/', include(auth_urls, namespace='auth')),
    url('^common/', include(common_urls, namespace='common')),
    url('^stylist/', include(stylist_urls, namespace='stylist')),
    url('^client/', include(client_urls, namespace='client')),
    url('^backdoor/', include(backdoor_urls, namespace='backdoor')),
    url('^webhooks/', include(webhooks_urls, namespace='webhooks')),
]
