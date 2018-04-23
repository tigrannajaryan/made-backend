from typing import NewType

from enum import IntEnum


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
