from decimal import Decimal
from enum import Enum, IntEnum
from typing import NamedTuple, NewType


class StrEnum(str, Enum):
    """Enum where members are also (and must be) strs"""

    def __str__(self):
        return self.value


class Weekday(IntEnum):
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6
    SUNDAY = 7


FBUserID = NewType('FBUserID', str)
FBAccessToken = NewType('FBAccessToken', str)


class UserRole(StrEnum):
    CLIENT = 'client'
    STYLIST = 'stylist'
    STAFF = 'staff'


class AppointmentPrices(NamedTuple):
    total_client_price_before_tax: Decimal
    total_tax: Decimal
    total_card_fee: Decimal
    grand_total: Decimal
    has_tax_included: bool
    has_card_fee_included: bool
    stylist_payout_amount: Decimal


class MobileOSType(StrEnum):
    IOS = 'ios'
    ANDROID = 'android'
