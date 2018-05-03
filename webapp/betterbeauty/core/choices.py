from model_utils import Choices

from django.utils.translation import ugettext_lazy as _

from .types import UserRole, Weekday

WEEKDAY = Choices(
    (Weekday.MONDAY.value, 'monday', _('Monday')),
    (Weekday.TUESDAY.value, 'tuesday', _('Tuesday')),
    (Weekday.WEDNESDAY.value, 'wednesday', _('Wednesday')),
    (Weekday.THURSDAY.value, 'thursday', _('Thursday')),
    (Weekday.FRIDAY.value, 'friday', _('Friday')),
    (Weekday.SATURDAY.value, 'saturday', _('Saturday')),
    (Weekday.SUNDAY.value, 'sunday', _('Sunday')),
)


USER_ROLE = Choices(
    (UserRole.CLIENT.value, 'client', _('Client')),
    (UserRole.STYLIST.value, 'stylist', _('Stylist')),
    (UserRole.STAFF.value, 'staff', _('Staff')),
)
