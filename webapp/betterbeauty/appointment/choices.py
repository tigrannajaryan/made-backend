from django.utils.translation import ugettext_lazy as _

from model_utils import Choices

from .types import AppointmentStatus

APPOINTMENT_STATUS_CHOICES = Choices(
    (AppointmentStatus.NEW.value, 'new', _('New')),
    (AppointmentStatus.CANCELLED_BY_CLIENT.value,
     'cancelled_by_client', _('Cancelled by client')),
    (AppointmentStatus.CANCELLED_BY_STYLIST.value,
     'cancelled_by_stylist', _('Cancelled by stylist')),
    (AppointmentStatus.NO_SHOW.value, 'no_show', _('No show')),
    (AppointmentStatus.CHECKED_OUT.value, 'checked_out', _('Client checked out')),
)
