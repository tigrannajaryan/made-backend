from typing import NewType

from enum import Enum, IntEnum


class StrEnum(str, Enum):
    """Enum where members are also (and must be) strs"""


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
