import datetime
import logging
from typing import Optional
from uuid import uuid4

from django.apps import apps
from django.contrib.gis.db.models import PointField
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from appointment.utils import get_appointments_in_datetime_range
from core.models import User
from integrations.gmaps import geo_code
from utils.models import SmartModel

logger = logging.getLogger(__name__)


class Client(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    birthday = models.DateField(blank=True, null=True)
    email = models.EmailField(null=True, unique=True)
    city = models.CharField(blank=True, null=True, max_length=64)
    state = models.CharField(blank=True, null=True, max_length=2)

    is_address_geocoded = models.BooleanField(default=False)
    last_geo_coded = models.DateTimeField(blank=True, null=True, default=None)

    def geo_code_address(self):
        geo_coded_address = geo_code(self.zip_code)
        if geo_coded_address:
            self.city = geo_coded_address.city
            self.state = geo_coded_address.state
            self.is_address_geocoded = True
        self.last_geo_coded = timezone.now()
        self.save(update_fields=[
            'city', 'state', 'is_address_geocoded', 'last_geo_coded'])

    class Meta:
        db_table = 'client'

    def __str__(self):
        return '{0} ({1})'.format(self.user.get_full_name(), self.user.phone)

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
            client__client=self
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


class ClientOfStylist(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    stylist = models.ForeignKey(
        'salon.Stylist', related_name='clients_of_stylist', on_delete=models.PROTECT)
    first_name = models.CharField(_('first name'), max_length=30, blank=True, null=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True, default=None)
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, blank=True, null=True, related_name='client_of_stylists')

    class Meta:
        db_table = 'client_of_stylist'
        unique_together = (("stylist", "phone"),
                           ("stylist", "client"),)

    def get_full_name(self):
        full_name = '{0} {1}'.format(self.first_name, self.last_name)
        return full_name.strip()

    def __str__(self):
        return self.get_full_name()


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
