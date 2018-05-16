from core.types import StrEnum


class AppointmentStatus(StrEnum):
    NEW = 'new'
    CANCELLED_BY_CLIENT = 'cancelled_by_client'
    CANCELLED_BY_STYLIST = 'cancelled_by_stylist'
    NO_SHOW = 'no_show'
    CHECKED_OUT = 'checked_out'
