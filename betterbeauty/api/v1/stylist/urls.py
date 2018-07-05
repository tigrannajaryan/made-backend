from django.conf.urls import url

from .views import (
    ClientSearchView,
    InvitationView,
    ServiceTemplateSetDetailsView,
    ServiceTemplateSetListView,
    StylistAppointmentListCreateView,
    StylistAppointmentPreviewView,
    StylistAppointmentRetrieveUpdateCancelView,
    StylistAvailabilityView,
    StylistDiscountsView,
    StylistHomeView,
    StylistServiceListView,
    StylistServicePricingView,
    StylistServiceView,
    StylistSettingsRetrieveView,
    StylistTodayView,
    StylistView,
)

app_name = 'stylist'

urlpatterns = [
    url('profile$', StylistView.as_view(), name='profile'),
    url('settings$', StylistSettingsRetrieveView.as_view(), name='settings'),
    url('service-template-sets$', ServiceTemplateSetListView.as_view()),
    url('service-template-sets/(?P<template_set_uuid>[0-9a-f\-]+)$',
        ServiceTemplateSetDetailsView.as_view()),
    url('services$', StylistServiceListView.as_view()),
    url('services/(?P<uuid>[0-9a-f\-]+)$', StylistServiceView.as_view()),
    url('services/pricing$', StylistServicePricingView.as_view()),
    url('availability/weekdays$', StylistAvailabilityView.as_view(), name='availability_weekdays'),
    url('discounts$', StylistDiscountsView.as_view(), name='discounts'),
    url('today$', StylistTodayView.as_view(), name='today'),
    url('home', StylistHomeView.as_view(), name='home'),
    url('appointments$', StylistAppointmentListCreateView.as_view()),
    url('appointments/preview$', StylistAppointmentPreviewView.as_view()),
    url('appointments/(?P<appointment_uuid>[0-9a-f\-]+)$',
        StylistAppointmentRetrieveUpdateCancelView.as_view()),
    url('invitations$', InvitationView.as_view(), name='invitation'),
    url('search-clients$', ClientSearchView.as_view(), name='search-client'),
]
