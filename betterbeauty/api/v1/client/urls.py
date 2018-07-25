from django.conf.urls import url

from api.v1.client.views import (
    AppointmentListCreateAPIView,
    ClientProfileView,
    PreferredStylistDeleteView,
    PreferredStylistListCreateView,
    SearchStylistView,
    StylistServicePriceView,
    StylistServicesView, AppointmentRetriveUpdateView)


app_name = 'client'

urlpatterns = [
    url('^profile$', ClientProfileView.as_view(), name='client-profile'),
    url('^search-stylists$', SearchStylistView.as_view(), name='search-stylist'),
    url('^preferred-stylists$',
        PreferredStylistListCreateView.as_view(), name='preferred-stylist'),
    url('^preferred-stylists/(?P<uuid>[0-9a-f\-]+)$',
        PreferredStylistDeleteView.as_view(), name='preferred-stylist-delete'),
    url('^stylists/(?P<uuid>[0-9a-f\-]+)/services',
        StylistServicesView.as_view(), name='stylist-services'),
    url('^services/pricing', StylistServicePriceView.as_view(), name='services-pricing'),

    url('^appointments$',
        AppointmentListCreateAPIView.as_view(), name='appointments'),
    url('^appointments/(?P<uuid>[0-9a-f\-]+)$',
        AppointmentRetriveUpdateView.as_view(), name='appointment')
]
