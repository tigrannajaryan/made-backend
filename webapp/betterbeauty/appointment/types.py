from enum import Enum


class AppointmentStatus(str, Enum):
    NEW = 'new'
    CANCELLED_BY_CLIENT = 'cancelled_by_client'
    CANCELLED_BY_STYLIST = 'cancelled_by_stylist'
    NO_SHOW = 'no_show'
    CHECKED_OUT = 'checked_out'
