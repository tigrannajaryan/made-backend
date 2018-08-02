import datetime
from typing import List, Optional

from django.db import models

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
            datetime_start_at__gte=datetime_from
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
