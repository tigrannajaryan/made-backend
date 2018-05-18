from .types import AppointmentStatus

APPOINTMENT_STYLIST_SETTABLE_STATUSES = [
    AppointmentStatus.NEW,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.CANCELLED_BY_STYLIST,
    AppointmentStatus.CHECKED_OUT,
]

APPOINTMENT_CLIENT_SETTABLE_STATUSES = [
    AppointmentStatus.NEW,
    AppointmentStatus.CANCELLED_BY_CLIENT,
]
