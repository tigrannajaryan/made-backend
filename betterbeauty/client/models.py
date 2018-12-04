import datetime
import logging
from typing import Optional
from uuid import uuid4

from django.apps import apps
from django.contrib.gis.db.models import PointField
from django.db import models
from django.db.models import Q
from django.utils import timezone

from appointment.types import AppointmentStatus
from appointment.utils import get_appointments_in_datetime_range
from core.models import User
from integrations.gmaps import GeoCode
from utils.models import SmartModel

from .types import CLIENT_PRIVACY_CHOICES, ClientPrivacy

logger = logging.getLogger(__name__)


class Client(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    email = models.EmailField(null=True, blank=True)
    city = models.CharField(blank=True, null=True, max_length=64)
    state = models.CharField(blank=True, null=True, max_length=25)
    country = models.CharField(max_length=20, blank=True, null=True)
    location = PointField(geography=True, null=True, blank=True)

    is_address_geocoded = models.BooleanField(default=False)
    last_geo_coded = models.DateTimeField(blank=True, null=True, default=None)

    privacy = models.CharField(
        max_length=16, choices=CLIENT_PRIVACY_CHOICES, default=ClientPrivacy.PUBLIC
    )
    google_integration_added_at = models.DateTimeField(null=True, blank=True, default=None)
    google_access_token = models.CharField(max_length=1024, null=True, blank=True, default=None)
    google_refresh_token = models.CharField(max_length=1024, null=True, blank=True, default=None)

    has_seen_educational_screens = models.BooleanField(default=False)

    created_at = models.DateTimeField(null=True, auto_now_add=True)

    def geo_code_address(self):
        geo_coded_address = GeoCode(self.zip_code).geo_code(country=self.country)
        if geo_coded_address:
            self.city = geo_coded_address.city
            self.state = geo_coded_address.state
            self.location = geo_coded_address.location
            self.is_address_geocoded = True
            logger.info('Geo-coding Success', exc_info=True)
        else:
            self.city = None
            self.state = None
            self.location = None
            self.is_address_geocoded = False
            logger.info("Geo-coding returned None")
        self.last_geo_coded = timezone.now()
        self.save(update_fields=[
            'city', 'state', 'is_address_geocoded', 'last_geo_coded', 'location'])

    class Meta:
        db_table = 'client'

    def __str__(self):
        return '{0} ({1})'.format(self.user.get_full_name(), self.user.phone)

    def get_profile_photo_url(self) -> Optional[str]:
        if self.user.photo:
            return self.user.photo.url
        return None

    def get_appointments_in_datetime_range(
            self,
            datetime_from: Optional[datetime.datetime]=None,
            datetime_to: Optional[datetime.datetime]=None,
            exclude_statuses=None,
            q_filter: Optional[models.Q]=None,
            **kwargs
    ) -> models.QuerySet:
        """
        Return appointments present in given datetime range.
        :param datetime_from: datetime at which first appointment is present
        :param datetime_to: datetime by which last appointment starts
        :param exclude_statuses: (optional) list of statuses to exclude
        :param kwargs: any optional filter kwargs to be applied
        :param q_filter: optional list of filters to apply
        :return: Resulting Appointment queryset
        """
        queryset = apps.get_model('appointment', 'Appointment').objects.filter(
            client=self, stylist__deactivated_at=None
        )

        appointments = get_appointments_in_datetime_range(
            queryset=queryset,
            datetime_from=datetime_from,
            datetime_to=datetime_to,
            exclude_statuses=exclude_statuses,
            **kwargs
        )

        if q_filter:
            appointments = appointments.filter(q_filter)

        return appointments.order_by('datetime_start_at')

    def get_past_appointments(self):
        current_now: datetime.datetime = timezone.now()
        last_midnight = (current_now).replace(hour=0, minute=0, second=0)
        next_midnight = (current_now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0)

        return self.get_appointments_in_datetime_range(
            datetime_from=None,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_STYLIST,
                AppointmentStatus.CANCELLED_BY_CLIENT,
            ],
            q_filter=(Q(datetime_start_at__lt=last_midnight) | Q(
                datetime_start_at__gte=last_midnight,
                datetime_start_at__lt=next_midnight,
                status=AppointmentStatus.CHECKED_OUT)),
        ).order_by('-datetime_start_at')

    def remove_google_oauth_token(self):
        """Completely remove access and refresh tokens to allow to re-add integration"""
        self.google_access_token = None
        self.google_refresh_token = None
        self.google_integration_added_at = None
        self.save(update_fields=[
            'google_access_token', 'google_refresh_token', 'google_integration_added_at'
        ])


class PreferredStylist(SmartModel):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='preferred_stylists')
    stylist = models.ForeignKey('salon.Stylist', on_delete=models.PROTECT)

    class Meta:
        db_table = 'preferred_stylist'
        unique_together = (("stylist", "client"),)


class StylistSearchRequest(models.Model):

    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    user_location = PointField(srid=4326, null=True)
    user_ip_addr = models.GenericIPAddressField(null=True)

    class Meta:
        db_table = 'stylist_search_request'
