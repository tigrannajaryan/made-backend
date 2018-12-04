import datetime
from io import TextIOBase
from typing import List, Optional

from django.db import models, transaction
from django.db.models import F

from .types import AppointmentStatus


def get_appointments_in_datetime_range(
        queryset: models.QuerySet,
        datetime_from: Optional[datetime.datetime] = None,
        datetime_to: Optional[datetime.datetime] = None,
        exclude_statuses: Optional[List[AppointmentStatus]] = None,
        **kwargs
) -> models.QuerySet:
    """
    Filter queryset of appointments based on given datetime range.
    :param queryset: Queryset to filter
    :param datetime_from: datetime at which first appointment is present
    :param datetime_to: datetime by which last appointment starts
    :param exclude_statuses: list of statuses to be excluded from the resulting query
    :param kwargs: any optional filter kwargs to be applied
    :return: Resulting Appointment queryset
    """

    if datetime_from is not None:
        queryset = queryset.filter(
            datetime_start_at__gt=datetime_from - models.F('stylist__service_time_gap')
        )

    if datetime_to is not None:
        queryset = queryset.filter(
            datetime_start_at__lt=datetime_to
        )

    if exclude_statuses:
        assert isinstance(exclude_statuses, list)
        queryset = queryset.exclude(
            status__in=exclude_statuses
        )
    return queryset.filter(**kwargs)


def appointments_to_insert_to_stylist_calendar() -> models.QuerySet:
    """
    Eligible appointments must match the following criteria:
    - stylist has google access token
    - appointment start is AFTER stylist added google integration
    - appointment is in NEW or Checked Out state
    - appointment wasn't added to stylist's google calendar before
    :return: queryset of appointments
    """
    from .models import Appointment
    eligible_appointments = Appointment.objects.filter(
        stylist__google_access_token__isnull=False,
        stylist__google_refresh_token__isnull=False,
        status__in=[AppointmentStatus.NEW, AppointmentStatus.CHECKED_OUT],
        stylist_google_calendar_id__isnull=True,
        datetime_start_at__gte=F('stylist__google_integration_added_at')
    )
    return eligible_appointments


def appointments_to_delete_from_stylist_calendar() -> models.QuerySet:
    """
    Find those appointments which are in cancelled state, but still have
    `stylist_google_calendar_id` field set.
    :return:
    """
    from .models import Appointment
    eligible_appointments = Appointment.objects.filter(
        stylist__google_access_token__isnull=False,
        stylist__google_refresh_token__isnull=False,
        status__in=[
            AppointmentStatus.CANCELLED_BY_STYLIST, AppointmentStatus.CANCELLED_BY_CLIENT],
        stylist_google_calendar_id__isnull=False
    )
    return eligible_appointments


def appointments_to_insert_to_client_calendar() -> models.QuerySet:
    """
    Eligible appointments must match the following criteria:
    - client has google access token
    - appointment start is AFTER client added google integration
    - appointment is in NEW or Checked Out state
    - appointment wasn't added to client's google calendar before
    :return: queryset of appointments
    """
    from .models import Appointment
    eligible_appointments = Appointment.objects.filter(
        client__google_access_token__isnull=False,
        client__google_refresh_token__isnull=False,
        status__in=[AppointmentStatus.NEW, AppointmentStatus.CHECKED_OUT],
        client_google_calendar_id__isnull=True,
        datetime_start_at__gte=F('client__google_integration_added_at')
    )
    return eligible_appointments


def appointments_to_delete_from_client_calendar() -> models.QuerySet:
    """
    Find those appointments which are in cancelled state, but still have
    `stylist_google_calendar_id` field set.
    :return:
    """
    from .models import Appointment
    eligible_appointments = Appointment.objects.filter(
        client__google_access_token__isnull=False,
        client__google_refresh_token__isnull=False,
        status__in=[
            AppointmentStatus.CANCELLED_BY_STYLIST, AppointmentStatus.CANCELLED_BY_CLIENT],
        client_google_calendar_id__isnull=False
    )
    return eligible_appointments


@transaction.atomic()
def generate_stylist_calendar_events_for_new_appointments(
        stdout: TextIOBase, dry_run: bool=False
):
    """
    Generate Google calendar events for all eligible appointments in the future.
    :param stdout: handle to stdout stream
    :param dry_run: whether or not to actually perform changes, or just print out
    """
    eligible_appointments = appointments_to_insert_to_stylist_calendar(
    ).select_for_update(skip_locked=True)

    for appointment in eligible_appointments.iterator():
        stdout.write('Going to create calendar event for {0}'.format(appointment))
        if not dry_run:
            appointment.create_stylist_google_calendar_event()


@transaction.atomic()
def clean_up_cancelled_stylist_calendar_events(
        stdout: TextIOBase, dry_run: bool=False
):
    """
    Cancel eligible google calendar events, and set appointments'
    stylist_google_calendar_id to None

    :param stdout: handle to stdout stream
    :param dry_run: whether or not to actually perform changes, or just print out
    """
    eligible_appointments = appointments_to_delete_from_stylist_calendar(
    ).select_for_update(skip_locked=True)
    for appointment in eligible_appointments.iterator():
        stdout.write('Going to cancel calendar event for {0}'.format(appointment))
        if not dry_run:
            appointment.cancel_stylist_google_calendar_event()


@transaction.atomic()
def generate_client_calendar_events_for_new_appointments(
        stdout: TextIOBase, dry_run: bool=False
):
    """
    Generate Google calendar events for all eligible appointments in the future.
    :param stdout: handle to stdout stream
    :param dry_run: whether or not to actually perform changes, or just print out
    """
    eligible_appointments = appointments_to_insert_to_client_calendar(
    ).select_for_update(skip_locked=True)

    for appointment in eligible_appointments.iterator():
        stdout.write('Going to create calendar event for {0}'.format(appointment))
        if not dry_run:
            appointment.create_client_google_calendar_event()


@transaction.atomic()
def clean_up_cancelled_client_calendar_events(
        stdout: TextIOBase, dry_run: bool=False
):
    """
    Cancel eligible google calendar events, and set appointments'
    client_google_calendar_id to None

    :param stdout: handle to stdout stream
    :param dry_run: whether or not to actually perform changes, or just print out
    """
    eligible_appointments = appointments_to_delete_from_client_calendar(
    ).select_for_update(skip_locked=True)
    for appointment in eligible_appointments.iterator():
        stdout.write('Going to cancel calendar event for {0}'.format(appointment))
        if not dry_run:
            appointment.cancel_client_google_calendar_event()
