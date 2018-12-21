from django.conf.urls import url

from .views import (
    AnalyticsSessionsView,
    AnalyticsViewsView,
    CommonStylistDetailView,
    IntegrationAddView,
    NotificationAckView,
    RegisterDeviceView,
    StylistInstagramPhotosRetrieveView,
    TemporaryImageUploadView,
    UnregisterDeviceView,
)

app_name = 'common'

urlpatterns = [
    url('^image/upload$', TemporaryImageUploadView.as_view(), name='temp_image_upload'),
    url('^register-device$', RegisterDeviceView.as_view(), name='register_device'),
    url('^unregister-device$', UnregisterDeviceView.as_view(), name='unregister_device'),
    url('^ack-push$', NotificationAckView.as_view(), name='acknowledge-push-notification'),
    url('^integrations$', IntegrationAddView.as_view(), name='integration-add'),
    url('^analytics/views$', AnalyticsViewsView.as_view(), name='analytics_views'),
    url('^analytics/sessions$', AnalyticsSessionsView.as_view(), name='analytics_sessions'),
    url('^stylist-profile/(?P<stylist_uuid>[0-9a-f\-]+)$',
        CommonStylistDetailView.as_view(), name='stylist-profile-detail'),
    url('^stylist/(?P<stylist_uuid>[0-9a-f\-]+)/instagram-photos',
        StylistInstagramPhotosRetrieveView.as_view(), name='instagram-photos'),
]
