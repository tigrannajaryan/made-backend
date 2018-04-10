from django.conf.urls import url

from .views import StylistView

urlpatterns = [
    url('profile/$', StylistView.as_view())
]
