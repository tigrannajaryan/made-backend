from django.db import transaction

from core.models import User
from core.types import Weekday
from salon.models import Stylist


def create_stylist_profile_for_user(user: User, **kwargs) -> Stylist:
    with transaction.atomic():
        stylist = Stylist.objects.create(user=user, **kwargs)
        for i in range(1, 8):
            stylist.get_or_create_weekday_availability(Weekday(i))
            stylist.get_or_create_weekday_discount(Weekday(i), 0)
        return stylist
