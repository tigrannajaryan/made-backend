from model_utils import Choices

from django.utils.translation import ugettext_lazy as _

from .types import Weekday

WEEKDAY = Choices(
    (Weekday.MONDAY, 'monday', _('Monday')),
    (Weekday.TUESDAY, 'tuesday', _('Tuesday')),
    (Weekday.WEDNESDAY, 'wednesday', _('Wednesday')),
    (Weekday.THURSDAY, 'thursday', _('Thursday')),
    (Weekday.FRIDAY, 'friday', _('Friday')),
    (Weekday.SATURDAY, 'saturday', _('Saturday')),
    (Weekday.SUNDAY, 'sunday', _('Sunday')),
)

CLIENT = 'client'
STYLIST = 'stylist'
STAFF = 'staff'

USER_ROLE = Choices(
    (CLIENT, 'client', _('Client')),
    (STYLIST, 'stylist', _('Stylist')),
    (STAFF, 'staff', _('Staff')),
)
