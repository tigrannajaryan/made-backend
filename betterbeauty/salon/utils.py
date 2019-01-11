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
    DiscountType,
)
from pricing.constants import COMPLETELY_BOOKED_DEMAND, PRICE_BLOCK_SIZE
from salon.models import Salon, Stylist, StylistAvailableWeekDay, StylistService
from salon.types import (
    ClientPriceOnDate,
    ClientPricingHint,
    DemandOnDate,
    LoyaltyDiscountTransitionInfo,
    PriceOnDate,
)


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

    for date_index, date in enumerate(dates):
        midnight = stylist.with_salon_tz(datetime.datetime.combine(date, datetime.time(0, 0)))
        next_midnight = midnight + datetime.timedelta(days=1)
        work_day_duration, stylist_weekday_availability = weekday_available_times[
            date.isoweekday()]
        # if stylist has specifically marked date as unavailable - reflect it
        has_special_date_unavailable = stylist.special_available_dates.filter(
            date=date, is_available=False
        ).exists()
        if has_special_date_unavailable:
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
        is_working_day: bool = is_stylist_weekday_available and not has_special_date_unavailable

        demand_on_date = (
            load_on_date_duration / work_day_duration
            if work_day_duration > datetime.timedelta(0)
            else COMPLETELY_BOOKED_DEMAND
        )
        # pricing experiment: add experimental pricing logic when discounts are gradually reduced
        # for dates which are closer to today:
        # Today: assume the demand is at least 75% even if it is lower
        # Tomorrow: assume the demand is at least 50% even if it is lower
        # The day after tomorrow: assume the demand is at least 25% even if it is lower
        # After that: use the real demand

        if date_index == 0:  # today
            demand_on_date = max(demand_on_date, 0.75)
        elif date_index == 1:  # tomorrow
            demand_on_date = max(demand_on_date, 0.5)
        elif date_index == 2:  # day after tomorrow
            demand_on_date = max(demand_on_date, 0.25)

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

    prices_and_dates: Iterable[PriceOnDate] = generate_prices_for_stylist_service(
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
        service: StylistService, client: Optional[Client], date: datetime.date,
        based_on_existing_service: Optional[AppointmentService]=None
) -> CalculatedPrice:
    """
    Calculate client's price and discount for a service on the given date, based
    either on discounts effective on the date, or copying discount percentage from
    another previously created service (based_on_existing_service)
    :param service: Service to calculate prices for
    :param client: Client for whom price is calculated
    :param date: Date on which service will happen
    :param based_on_existing_service: if supplied - discounts will be copied from it
    :return:
    """
    if based_on_existing_service is not None:
        applied_discount: DiscountType = based_on_existing_service.applied_discount
        discount_percentage: int = based_on_existing_service.discount_percentage
        price = service.regular_price * Decimal(1 - discount_percentage / 100.0)
        client_price: float = float(Decimal(price).quantize(1, ROUND_HALF_UP))
        return CalculatedPrice.build(
            applied_discount=applied_discount,
            discount_percentage=discount_percentage,
            price=client_price
        )

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
        if 'salon' not in kwargs:
            kwargs['salon'] = Salon.objects.create()
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


def get_loyalty_discount_for_week(stylist: Stylist, week_cnt: int) -> int:
    """Return loyalty discount that stylist offers within week_cnt weeks after last booking"""
    if week_cnt not in range(1, 5):
        return 0
    loyalty_discount_field_names = {
        1: 'rebook_within_1_week_discount_percent',
        2: 'rebook_within_2_weeks_discount_percent',
        3: 'rebook_within_3_weeks_discount_percent',
        4: 'rebook_within_4_weeks_discount_percent',
    }
    field_name = loyalty_discount_field_names[week_cnt]
    return getattr(stylist, field_name)


def get_current_loyalty_discount(stylist, client) -> LoyaltyDiscountTransitionInfo:
    last_appointment = get_last_appointment_for_client(stylist, client)
    MAX_WEEKS_TO_CHECK = 4
    if not last_appointment:
        return LoyaltyDiscountTransitionInfo(
            current_discount_percent=0,
            transitions_to_percent=0,
            transitions_at=None
        )
    current_now = timezone.now()
    last_visit_datetime = last_appointment.datetime_start_at
    for week in range(1, MAX_WEEKS_TO_CHECK + 1):
        loyalty_discount_for_week = get_loyalty_discount_for_week(stylist, week_cnt=week)
        if last_visit_datetime + datetime.timedelta(
                weeks=week
        ) > current_now and loyalty_discount_for_week:
            current_discount = loyalty_discount_for_week
            # try to find what it transitions to. Iterate over remaining discounts
            # until we find next non-zero discount (if it exists)
            transitions_at = last_visit_datetime + datetime.timedelta(weeks=week)
            transitions_to = 0
            next_week_cnt = 1
            while week + next_week_cnt <= MAX_WEEKS_TO_CHECK and transitions_to <= 0:
                transitions_to = get_loyalty_discount_for_week(stylist, week + next_week_cnt)
                next_week_cnt += 1
            return LoyaltyDiscountTransitionInfo(
                current_discount_percent=current_discount,
                transitions_to_percent=transitions_to,
                transitions_at=transitions_at
            )
    return LoyaltyDiscountTransitionInfo(
        current_discount_percent=0,
        transitions_to_percent=0,
        transitions_at=None
    )


def get_date_with_lowest_price_on_current_week(
        stylist: Stylist,
        prices_on_dates: List[ClientPriceOnDate]
) -> Optional[datetime.date]:
    """
    Find the lowest, non-repeating price on this week and return it if it's today or is
    in the future. Return None otherwise.

    Non-repeating means that we need indeed lowest price, e.g. 1.0 out of [1.0, 2.0, 3.0]
    If there's repeating low price, e.g. [1.0, 2.0, 1.0, 3.0] - then we will return None
    """

    # filter out prices of this week only
    current_date = stylist.with_salon_tz(timezone.now()).date()
    begin_of_week_date = current_date - datetime.timedelta(days=current_date.isoweekday() - 1)
    end_of_week_date = current_date + datetime.timedelta(days=7 - current_date.isoweekday())
    this_week_prices: List[ClientPriceOnDate] = list(filter(
        lambda price_on_date: begin_of_week_date <= price_on_date.date <= end_of_week_date,
        prices_on_dates
    ))
    # There may be a situation when we don't have enough data for this week; return None in
    # this case
    if len(this_week_prices) < 2:
        return None
    # we need to find the ultimate, non-repeating minimum price. Let's sort this week's
    # prices; the first element will be the minimum, but we must check if the second element
    # is equal to it price-wise (which would mean that there's no single lowest price)
    prices_on_days_sorted = sorted(this_week_prices, key=lambda price_on_date: price_on_date.price)
    if prices_on_days_sorted[0].price == prices_on_days_sorted[1].price:
        # there's no local minimum: there are at least 2 days with equally low price
        return None
    if prices_on_days_sorted[0].date < current_date:
        # the lowest price is already in the past
        return None
    return prices_on_days_sorted[0].date


def generate_client_pricing_hints(
        client: Client, stylist: Stylist, prices_on_dates: List[ClientPriceOnDate]
) -> List[ClientPricingHint]:
    hints: List[ClientPricingHint] = []
    MIN_DAYS_BEFORE_LOYALTY_DISCOUNT_HINT = 3
    loyalty_discount: LoyaltyDiscountTransitionInfo = get_current_loyalty_discount(stylist, client)
    # 1. Check if current loyalty discount is about to transition to lower level
    if loyalty_discount.current_discount_percent and loyalty_discount.transitions_at:
        days_before_discount_ends = (loyalty_discount.transitions_at - timezone.now()).days
        if days_before_discount_ends <= MIN_DAYS_BEFORE_LOYALTY_DISCOUNT_HINT:
            if loyalty_discount.transitions_to_percent:
                # loyalty discount is about to transition to different non-zero percentage
                hints.append(
                    ClientPricingHint(
                        priority=1,
                        hint=(
                            'Your {current_discount}% loyalty discount '
                            'reduces to {next_discount}% on {date}.'
                        ).format(
                            current_discount=loyalty_discount.current_discount_percent,
                            next_discount=loyalty_discount.transitions_to_percent,
                            date=loyalty_discount.transitions_at.strftime('%b, %-d')
                        )
                    )
                )
            # loyalty discount just ends
            else:
                hints.append(
                    ClientPricingHint(
                        priority=1,
                        hint='Book soon, your loyalty discount expires on {date}.'.format(
                            date=loyalty_discount.transitions_at.strftime('%b, %-d')
                        )
                    )
                )
    # 2. Check if there's a local minimum of price between current now and the
    # end of the week
    lowest_price_date = get_date_with_lowest_price_on_current_week(
        stylist=stylist,
        prices_on_dates=prices_on_dates
    )
    if lowest_price_date is not None:
        hints.append(
            ClientPricingHint(
                priority=2,
                hint='Best price this week is {weekday}.'.format(
                    weekday=lowest_price_date.strftime('%A')
                )
            )
        )
    # for now, we will only return the first element
    return hints[:1]
