import datetime
from typing import NamedTuple

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
