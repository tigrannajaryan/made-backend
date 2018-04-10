from django.conf.urls import include, url

from .auth import urls as auth_urls
from .stylist import urls as stylist_urls

urlpatterns = [
    url('auth/', include(auth_urls)),
    url('stylist/', include(stylist_urls)),
]
