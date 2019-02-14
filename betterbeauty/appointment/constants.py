from .types import AppointmentStatus

DEFAULT_HAS_TAX_INCLUDED = True

DEFAULT_HAS_CARD_FEE_INCLUDED = False

APPOINTMENT_STYLIST_SETTABLE_STATUSES = [
    AppointmentStatus.NEW,
    AppointmentStatus.NO_SHOW,
    AppointmentStatus.CANCELLED_BY_STYLIST,
    AppointmentStatus.CHECKED_OUT,
]

APPOINTMENT_CLIENT_SETTABLE_STATUSES = [
    AppointmentStatus.NEW,
    AppointmentStatus.CANCELLED_BY_CLIENT,
    AppointmentStatus.CHECKED_OUT,
]


class ErrorMessages(object):
    ERR_APPOINTMENT_IN_THE_PAST = 'err_appointment_in_the_past'
    ERR_APPOINTMENT_INTERSECTION = 'err_appointment_intersection'
    ERR_APPOINTMENT_OUTSIDE_WORKING_HOURS = 'err_appointment_outside_working_hours'
    ERR_APPOINTMENT_NON_WORKING_DAY = 'err_appointment_non_working_day'
    ERR_SERVICE_DOES_NOT_EXIST = 'err_service_does_not_exist'
    ERR_SERVICE_REQUIRED = 'err_service_required'
    ERR_NON_ADDON_SERVICE_REQUIRED = 'err_non_addon_service_required'
    ERR_CLIENT_DOES_NOT_EXIST = 'err_client_does_not_exist'
    ERR_STYLIST_DOES_NOT_EXIST = 'err_stylist_does_not_exist'
    ERR_STATUS_NOT_ALLOWED = 'err_status_not_allowed'
    ERR_NO_SECOND_CHECKOUT = 'err_no_second_checkout'
    ERR_APPOINTMENT_DOESNT_EXIST = 'err_appointment_does_not_exist'
    ERR_NOT_A_PREFERRED_STYLIST = 'err_not_a_preferred_stylist'
    ERR_CANNOT_MODIFY_APPOINTMENT = 'err_cannot_modify_appointment'
