import datetime
from typing import NamedTuple, Tuple

from core.types import StrEnum
from pricing import CalculatedPrice


class InvitationStatus(StrEnum):
    INVITED = 'invited'
    ACCEPTED = 'accepted'


class DemandOnDate(NamedTuple):
    demand: float
    is_fully_booked: bool
    is_working_day: bool


class PriceOnDate(NamedTuple):
    date: datetime.date
    calculated_price: CalculatedPrice
    is_fully_booked: bool
    is_working_day: bool


class TimeSlotAvailability(object):

    def __init__(self, start: datetime.datetime, end: datetime.datetime,
                 is_booked: bool = False) -> None:
        self.start = start
        self.end = end
        self.is_booked = is_booked


TimeSlot = Tuple[datetime.time, datetime.time]
