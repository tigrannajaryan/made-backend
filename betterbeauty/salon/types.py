import datetime
from typing import NamedTuple, Optional, Tuple

from core.types import StrEnum
from pricing import CalculatedPrice, DiscountType


class InvitationStatus(StrEnum):
    INVITED = 'invited'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'


class DemandOnDate(NamedTuple):
    demand: float
    is_fully_booked: bool
    is_working_day: bool


class PriceOnDate(NamedTuple):
    date: datetime.date
    calculated_price: CalculatedPrice
    is_fully_booked: bool
    is_working_day: bool


class ClientPriceOnDate(NamedTuple):
    date: datetime.date
    is_fully_booked: bool
    is_working_day: bool
    price: int
    discount_type: Optional[DiscountType]


class ClientPricingHint(NamedTuple):
    priority: int
    hint: str


class TimeSlotAvailability(object):

    def __init__(self, start: datetime.datetime, end: datetime.datetime,
                 is_booked: bool = False) -> None:
        self.start = start
        self.end = end
        self.is_booked = is_booked


TimeSlot = Tuple[datetime.time, datetime.time]


class LoyaltyDiscountTransitionInfo(NamedTuple):
    current_discount_percent: int
    transitions_to_percent: int
    transitions_at: Optional[datetime.datetime]


class DealOfWeekError(StrEnum):
    ERR_DATE_TOO_CLOSE = 'err_date_too_close'
    ERR_PERCENTAGE_TOO_LOW = 'err_percentage_too_low'
