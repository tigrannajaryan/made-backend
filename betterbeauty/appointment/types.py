from model_utils import Choices

from core.types import StrEnum


class AppointmentStatus(StrEnum):
    NEW = 'new'
    CANCELLED_BY_CLIENT = 'cancelled_by_client'
    CANCELLED_BY_STYLIST = 'cancelled_by_stylist'
    NO_SHOW = 'no_show'
    CHECKED_OUT = 'checked_out'


class RatingValues(StrEnum):
    THUMBS_DOWN = 0
    THUMBS_UP = 1


RATINGS_CHOICES = Choices(
    (RatingValues.THUMBS_DOWN.value, 0, 0, ),
    (RatingValues.THUMBS_UP.value, 1, 1),
)
