from django.conf.urls import url

from api.v1.client.views import (
    AppointmentListCreateAPIView,
    AppointmentPreviewView,
    AppointmentRetriveUpdateView,
    AvailableTimeSlotView,
    ClientProfileView,
    DeclineInvitationView,
    HistoryView,
    HomeView,
    InvitationView,
    PreferredStylistDeleteView,
    PreferredStylistListCreateView,
    SearchStylistView,
    StylistFollowersView,
    StylistServicePriceView,
    StylistServicesView,
)


app_name = 'client'

urlpatterns = [
    url('^profile$', ClientProfileView.as_view(), name='client-profile'),
    url('^home$', HomeView.as_view(), name='home'),
    url('^history$', HistoryView.as_view(), name='history'),
    url('^search-stylists$', SearchStylistView.as_view(), name='search-stylist'),
    url('^preferred-stylists$',
        PreferredStylistListCreateView.as_view(), name='preferred-stylist'),
    url('^preferred-stylists/(?P<uuid>[0-9a-f\-]+)$',
        PreferredStylistDeleteView.as_view(), name='preferred-stylist-delete'),
    url('^stylists/(?P<uuid>[0-9a-f\-]+)/services$',
        StylistServicesView.as_view(), name='stylist-services'),
    url('^stylists/(?P<stylist_uuid>[0-9a-f\-]+)/followers$',
        StylistFollowersView.as_view(), name='stylist-followers'),
    url('^services/pricing$', StylistServicePriceView.as_view(), name='services-pricing'),
    url('^available-times$', AvailableTimeSlotView.as_view(), name='available-times'),

    url('^appointments$',
        AppointmentListCreateAPIView.as_view(), name='appointments'),
    url('^appointments/preview$',
        AppointmentPreviewView.as_view(), name='appointments-preview'),
    url('^appointments/(?P<uuid>[0-9a-f\-]+)$',
        AppointmentRetriveUpdateView.as_view(), name='appointment'),
    url('^invitations$',
        InvitationView.as_view(), name='client-invitation'),
    url('^invitations/(?P<uuid>[0-9a-f\-]+)$',
        DeclineInvitationView.as_view(), name='decline-invitation'),
]
