from django.conf.urls import url

from .views import (
    StylistView,
    StylistServiceView,
    StylistServiceListView,
    ServiceTemplateSetListView,
    ServiceTemplateSetDetailsView,
)

app_name = 'stylist'

urlpatterns = [
    url('profile$', StylistView.as_view(), name='profile'),
    url('service-template-sets$', ServiceTemplateSetListView.as_view()),
    url('service-template-sets/(?P<template_set_uuid>[0-9a-f\-]+)$',
        ServiceTemplateSetDetailsView.as_view()),
    url('services$', StylistServiceListView.as_view()),
    url('services/(?P<service_pk>\d+)$', StylistServiceView.as_view()),
]
