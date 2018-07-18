from django.conf.urls import url

from api.v1.client.views import (
    ClientProfileView,
    PreferredStylistDeleteView,
    PreferredStylistListCreateView
)

app_name = 'client'

urlpatterns = [
    url('^profile$', ClientProfileView.as_view(), name='client-profile'),
    url('^preferred-stylists$',
        PreferredStylistListCreateView.as_view(), name='preferred-stylist'),
    url('^preferred-stylists/(?P<uuid>[0-9a-f\-]+)$',
        PreferredStylistDeleteView.as_view(), name='preferred-stylist-delete'),
]
