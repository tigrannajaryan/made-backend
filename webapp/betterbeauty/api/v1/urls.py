from django.conf.urls import include, url

from .auth import urls as auth_urls
from .stylist import urls as stylist_urls

app_name = 'v1'

urlpatterns = [
    url('auth/', include(auth_urls, namespace='auth')),
    url('stylist/', include(stylist_urls, namespace='stylist')),
]
