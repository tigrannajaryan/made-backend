import datetime
import uuid
from decimal import Decimal, ROUND_HALF_UP
from itertools import compress
from typing import Dict, Iterable, List, Optional, Tuple

from django.db import models, transaction
from django.utils import timezone

from appointment.constants import AppointmentStatus
from appointment.models import Appointment, AppointmentService
from client.constants import END_OF_DAY_BUFFER_TIME_IN_MINUTES
from client.models import Client
from core.constants import (
    DEFAULT_FIRST_TIME_BOOK_DISCOUNT_PERCENT,
    DEFAULT_REBOOK_WITHIN_1_WEEK_DISCOUNT_PERCENT,
    DEFAULT_REBOOK_WITHIN_2_WEEKS_DISCOUNT_PERCENT,
    DEFAULT_REBOOK_WITHIN_3_WEEKS_DISCOUNT_PERCENT,
    DEFAULT_REBOOK_WITHIN_4_WEEKS_DISCOUNT_PERCENT,
    DEFAULT_WEEKDAY_DISCOUNT_PERCENTS,
)
from core.models import User
from core.types import UserRole, Weekday
from pricing import (
    calc_client_prices,
    CalculatedPrice,
    DiscountSettings,
)
from pricing.constants import COMPLETELY_BOOKED_DEMAND, PRICE_BLOCK_SIZE
from salon.models import Stylist, StylistAvailableWeekDay, StylistService
from salon.types import ClientPriceOnDate, DemandOnDate, PriceOnDate


def get_weekday_available_times(stylist: Stylist) -> Dict[int, Tuple[
        datetime.timedelta, StylistAvailableWeekDay]]:

    weekday_available_times = {}

    # generate time availability based on weekday to avoid multiple DB requests
    for weekday in range(1, 8):
        available_weekday: StylistAvailableWeekDay = stylist.available_days.filter(
            weekday=weekday
        ).last()
        if not available_weekday:
            weekday_available_times.update({
                weekday: (datetime.timedelta(0), available_weekday)
            })
        else:
            weekday_available_times.update({
                weekday: (available_weekday.get_available_time(), available_weekday)
            })

    return weekday_available_times


def generate_demand_list_for_stylist(
        stylist: Stylist, dates: List[datetime.date]
) -> List[DemandOnDate]:
    """
    Generate list of NamedTuples with demand (0..1 float), is_fully_booked(boolean),
    is_working_day(boolean), for each date supplied. Demand is generated
    based on formula: appointment_count * service_time_gap / available_time_during_day.
    If resulting demand value is > 1, we set it to 1. If no time is available during
    a day (or stylist is just unavailable on particular date) demand value will also
    be equal to 1
    """
    weekday_available_times = get_weekday_available_times(stylist)

    time_gap = stylist.service_time_gap
    demand_list = []

    for date in dates:
        midnight = stylist.with_salon_tz(datetime.datetime.combine(date, datetime.time(0, 0)))
        next_midnight = midnight + datetime.timedelta(days=1)
        work_day_duration, stylist_weekday_availability = weekday_available_times[
            date.isoweekday()]
        # if stylist has specifically marked date as unavailable - reflect it
        if stylist.special_available_dates.filter(
                date=date, is_available=False
        ).exists():
            work_day_duration = datetime.timedelta(0)
            stylist_weekday_availability = None
        load_on_date_duration = stylist.appointments.filter(
            datetime_start_at__gte=midnight, datetime_start_at__lt=next_midnight,
        ).exclude(status__in=[
            AppointmentStatus.CANCELLED_BY_STYLIST,
            AppointmentStatus.CANCELLED_BY_CLIENT]
        ).count() * time_gap
        is_stylist_weekday_available: bool = (
            stylist_weekday_availability.is_available if stylist_weekday_availability else False)
        has_special_date_unavailable = stylist.special_available_dates.filter(
            date=date, is_available=False
        ).exists()
        is_working_day: bool = is_stylist_weekday_available and not has_special_date_unavailable

        demand_on_date = (
            load_on_date_duration / work_day_duration
            if work_day_duration > datetime.timedelta(0)
            else COMPLETELY_BOOKED_DEMAND
        )

        # similar to demand_on_date which calculates the demand on the whole day,
        # we also need to calculate the demand during working hours to determine `is_fully_booked`
        if is_working_day:
            weekday_start_time = stylist.with_salon_tz(datetime.datetime.combine(
                date, stylist_weekday_availability.work_start_at))
            weekday_end_time = stylist.with_salon_tz(datetime.datetime.combine(
                date, stylist_weekday_availability.work_end_at))

            load_on_working_date_duration = stylist.appointments.filter(
                datetime_start_at__gte=weekday_start_time,
                datetime_start_at__lt=weekday_end_time,
            ).exclude(status__in=[
                AppointmentStatus.CANCELLED_BY_STYLIST,
                AppointmentStatus.CANCELLED_BY_CLIENT]
            ).count() * time_gap

        else:
            load_on_working_date_duration = datetime.timedelta(seconds=0)

        demand_on_working_hours = (
            load_on_working_date_duration / work_day_duration
            if work_day_duration > datetime.timedelta(0)
            else COMPLETELY_BOOKED_DEMAND
        )

        is_fully_booked: bool = False

        # Technically, there may be a situation of overbooking, which may cause actual
        # demand be > 1; in this case we'll cast it to 1 manually
        if demand_on_date > 1:
            demand_on_date = 1

        if is_working_day and demand_on_working_hours == COMPLETELY_BOOKED_DEMAND:
            is_fully_booked = True

        demand = DemandOnDate(
            demand=demand_on_date,
            is_fully_booked=is_fully_booked,
            is_working_day=is_working_day
        )
        demand_list.append(demand)
    return demand_list


def get_last_appointment_for_client(
    stylist: Stylist, client: Client
) -> Optional[Appointment]:
    """Return last checked out appointment between stylist and client"""
    last_appointment: Optional[Appointment] = Appointment.objects.filter(
        status__in=[AppointmentStatus.CHECKED_OUT],
        stylist=stylist,
        client=client,
        datetime_start_at__lte=timezone.now()
    ).order_by('datetime_start_at').last()
    return last_appointment


def get_last_visit_date_for_client(
        stylist: Stylist, client: Client
) -> Optional[datetime.date]:
    """Return last checked out appointment date between stylist and client"""
    last_appointment = get_last_appointment_for_client(
        stylist=stylist, client=client
    )

    if last_appointment:
        return last_appointment.datetime_start_at.date()
    return None


def generate_discount_settings_for_stylist(
        stylist: Stylist
) -> DiscountSettings:
    """Translate Stylist's discount settings to DiscountSettings object"""
    discounts = DiscountSettings()
    discounts.weekday_discounts = {
        Weekday(discount.weekday): discount.discount_percent
        for discount in stylist.weekday_discounts.all()
    }

    discounts.first_visit_percentage = stylist.first_time_book_discount_percent

    discounts.revisit_within_1week_percentage = (
        stylist.rebook_within_1_week_discount_percent
    )
    discounts.revisit_within_2week_percentage = (
        stylist.rebook_within_2_weeks_discount_percent
    )
    discounts.revisit_within_3week_percentage = (
        stylist.rebook_within_3_weeks_discount_percent
    )
    discounts.revisit_within_4week_percentage = (
        stylist.rebook_within_4_weeks_discount_percent
    )
    discounts.maximum_discount = stylist.maximum_discount
    discounts.is_maximum_discount_enabled = (
        stylist.is_maximum_discount_enabled
    )
    return discounts


def generate_prices_for_stylist_service(
        services: List[StylistService],
        client: Optional[Client],
        exclude_fully_booked: bool=False,
        exclude_unavailable_days: bool=False
) -> Iterable[PriceOnDate]:
    """
    Generate prices for given stylist, client and service for PRICE_BLOCK_SIZE days ahead

    :param service: Service to generate prices for
    :param client: (optional) Client object, if omitted no client-specific discounts will apply
    :param exclude_fully_booked: whether or not remove fully booked dates
    :param exclude_unavailable_days: whether or not remove unavailable dates
    :return: Iterator over (date, CalculatedPrice, fully_booked boolean)
    """
    stylist = services[0].stylist

    last_visit_date = get_last_visit_date_for_client(
        stylist, client
    ) if client else None

    today = stylist.get_current_now().date()
    dates_list = [today + datetime.timedelta(days=i) for i in range(0, PRICE_BLOCK_SIZE)]
    demand_on_dates = generate_demand_list_for_stylist(stylist=stylist, dates=dates_list)

    demand_list = [x.demand for x in demand_on_dates]

    discounts = generate_discount_settings_for_stylist(stylist)

    prices_list = calc_client_prices(
        stylist.salon.timezone,
        discounts,
        last_visit_date,
        [float(x.regular_price) for x in services],
        demand_list
    )

    is_fully_booked_list = [d.is_fully_booked for d in demand_on_dates]
    is_working_day_list = [d.is_working_day for d in demand_on_dates]
    prices_on_dates: Iterable[PriceOnDate] = [PriceOnDate._make(x) for x in zip(
        dates_list, prices_list, is_fully_booked_list, is_working_day_list)]
    if exclude_fully_booked:
        # remove dates where demand is equal to COMPLETELY_BOOKED_DEMAND
        prices_on_dates = compress(prices_on_dates, is_fully_booked_list)

    if exclude_unavailable_days:
        # remove dates where demand is equal to UNAVAILABLE_DEMAND
        prices_on_dates = compress(prices_on_dates, is_working_day_list)

    return prices_on_dates


def generate_client_prices_for_stylist_services(
        stylist: Stylist,
        services: List[StylistService],
        client: Optional[Client],
        exclude_fully_booked: bool=False,
        exclude_unavailable_days: bool=False
) -> List[ClientPriceOnDate]:
    prices_and_dates = generate_prices_for_stylist_service(
        services, client, exclude_fully_booked, exclude_unavailable_days
    )
    client_prices_on_dates: List[ClientPriceOnDate] = []
    for obj in prices_and_dates:
        availability_on_day = stylist.available_days.filter(
            weekday=obj.date.isoweekday(),
            is_available=True).last() if obj.date == stylist.get_current_now().date() else None
        stylist_eod = stylist.salon.timezone.localize(
            datetime.datetime.combine(
                date=obj.date, time=availability_on_day.work_end_at
            )) if availability_on_day else None
        if not stylist_eod or stylist.get_current_now() < (
                stylist_eod - stylist.service_time_gap -
                datetime.timedelta(minutes=END_OF_DAY_BUFFER_TIME_IN_MINUTES)):
            client_prices_on_dates.append(ClientPriceOnDate(
                date=obj.date,
                price=int(Decimal(obj.calculated_price.price).quantize(0, ROUND_HALF_UP)),
                is_fully_booked=obj.is_fully_booked,
                is_working_day=obj.is_working_day,
                discount_type=obj.calculated_price.applied_discount,

            ))
    return client_prices_on_dates


def calculate_price_and_discount_for_client_on_date(
        service: StylistService, client: Optional[Client], date: datetime.date
) -> CalculatedPrice:

    price_on_dates: Iterable[PriceOnDate] = (
        generate_prices_for_stylist_service(
            services=[service, ], client=client,
            exclude_fully_booked=False,
            exclude_unavailable_days=False
        ))

    prices: Dict[datetime.date, CalculatedPrice] = dict(
        (m.date, m.calculated_price) for m in price_on_dates)

    if date in prices:
        return prices[date]
    # Return base price if day does not appear to be available for booking
    calculated_price = CalculatedPrice.build(
        price=float(Decimal(service.regular_price).quantize(0, ROUND_HALF_UP)),
        applied_discount=None, discount_percentage=0
    )
    return calculated_price


def create_stylist_profile_for_user(user: User, **kwargs) -> Stylist:
    with transaction.atomic():
        kwargs.update(
            {
                'rebook_within_1_week_discount_percent':
                    DEFAULT_REBOOK_WITHIN_1_WEEK_DISCOUNT_PERCENT,
                'rebook_within_2_weeks_discount_percent':
                    DEFAULT_REBOOK_WITHIN_2_WEEKS_DISCOUNT_PERCENT,
                'rebook_within_3_weeks_discount_percent':
                    DEFAULT_REBOOK_WITHIN_3_WEEKS_DISCOUNT_PERCENT,
                'rebook_within_4_weeks_discount_percent':
                    DEFAULT_REBOOK_WITHIN_4_WEEKS_DISCOUNT_PERCENT,
                'first_time_book_discount_percent':
                    DEFAULT_FIRST_TIME_BOOK_DISCOUNT_PERCENT
            }
        )
        stylist = Stylist.objects.create(user=user, **kwargs)
        for i in range(1, 8):
            stylist.get_or_create_weekday_availability(Weekday(i))
            discount = stylist.get_or_create_weekday_discount(
                Weekday(i)
            )
            discount.discount_percent = DEFAULT_WEEKDAY_DISCOUNT_PERCENTS[i]
            discount.save(update_fields=['discount_percent', ])
        if UserRole.STYLIST.value not in user.role:
            current_roles: list = user.role if user.role else []
            current_roles.append(UserRole.STYLIST.value)
            user.role = current_roles
            user.save(update_fields=['role', ])
        return stylist


def get_most_popular_service(stylist: Stylist) -> Optional[StylistService]:
    """Return service which has max amount of inclusions to appointments"""
    appt_service_by_popularity = AppointmentService.objects.filter(
        appointment__stylist=stylist
    ).values('service_uuid').annotate(
        num_inclusions=models.Count('service_uuid')).order_by('-num_inclusions')
    # service with such UUID may no longer exist, so we need to find
    # first which still has corresponding stylist service
    for service in appt_service_by_popularity:
        if stylist.services.filter(
                uuid=service['service_uuid'], deleted_at__isnull=True
        ).exists():
            return stylist.services.get(uuid=service['service_uuid'])
    return None


def get_default_service_uuids(
        stylist: Stylist, client: Optional[Client]
) -> List[uuid.UUID]:
    """
    Return services to display initial pricing for, if services list is not explicitly
    provided, using the following rules:
    1) last service client booked. If they haven’t booked yet, then
    2) service most often booked for that stylist. If stylist hasn’t had
       anything booked yet, then
    3) first service on the stylist list of services
    """
    if client:
        last_appointment: Optional[Appointment] = get_last_appointment_for_client(
            stylist=stylist, client=client
        )
        if last_appointment:
            service_uuids = [
                s.service_uuid for s in last_appointment.services.all()
                if stylist.services.filter(uuid=s.service_uuid).exists()]
            if service_uuids:
                return service_uuids
    most_popular_service: Optional[
        StylistService
    ] = get_most_popular_service(stylist=stylist)
    if most_popular_service:
        return [most_popular_service.uuid, ]
    if stylist.services.count():
        return [stylist.services.first().uuid, ]
    return []


def has_bookable_slots_with_discounts(stylist: Stylist, max_dates_to_look: int=7):
    """
    Return True if stylist is bookable and has at least one available slot
    with non-zero discounts in the next `max_dates_to_look` days (excluding today)
    :param stylist: Stylist to check
    :param max_dates_to_look: for how many days in the future to look
    :return: True if has bookable discounted slots, False otherwise
    """

    today = stylist.with_salon_tz(timezone.now()).date()
    has_available_slots_with_discounts = False
    day_count = 0
    # go over next 7 days, and find first available slot on a day for which stylist
    # has non-zero discount
    while not has_available_slots_with_discounts and day_count <= max_dates_to_look:
        day_count += 1
        date_to_verify = today + datetime.timedelta(days=day_count)
        available_slots = list(filter(
            lambda a: not a.is_booked,
            stylist.get_available_slots(date=date_to_verify)
        ))
        available_slot_count = len(available_slots)
        if available_slot_count:
            has_discount_on_this_day = stylist.get_weekday_discount_percent(
                Weekday(date_to_verify.isoweekday())
            ) > 0
            if has_discount_on_this_day:
                has_available_slots_with_discounts = True
    return has_available_slots_with_discounts
