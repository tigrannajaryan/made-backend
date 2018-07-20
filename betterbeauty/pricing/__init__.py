from datetime import date, datetime, timedelta, tzinfo
from enum import Enum
from typing import Dict, List, NamedTuple, Optional

from model_utils import Choices

from core.types import Weekday

from .constants import (
    DISCOUNT_GRANULARIZATION,
    PRICE_BLOCK_SIZE,
)


class DiscountType(Enum):
    FIRST_BOOKING = 'first_booking'
    REVISIT_WITHIN_1WEEK = 'revisit_within_1_week'
    REVISIT_WITHIN_2WEEK = 'revisit_within_2_weeks'
    REVISIT_WITHIN_3WEEK = 'revisit_within_3_weeks'
    REVISIT_WITHIN_4WEEK = 'revisit_within_4_weeks'
    REVISIT_WITHIN_5WEEK = 'revisit_within_5_weeks'
    REVISIT_WITHIN_6WEEK = 'revisit_within_6_weeks'
    WEEKDAY = 'weekday'


DISCOUNT_TYPE_CHOICES = Choices(
    (DiscountType.FIRST_BOOKING.value, 'first_booking', 'First Booking'),
    (DiscountType.REVISIT_WITHIN_1WEEK.value, 'revisit_within_1_week', 'Revisit within 1 week'),
    (DiscountType.REVISIT_WITHIN_2WEEK.value, 'revisit_within_2_weeks', 'Revisit within 2 weeks'),
    (DiscountType.REVISIT_WITHIN_3WEEK.value, 'revisit_within_3_weeks', 'Revisit within 3 weeks'),
    (DiscountType.REVISIT_WITHIN_4WEEK.value, 'revisit_within_4_weeks', 'Revisit within 4 weeks'),
    (DiscountType.REVISIT_WITHIN_5WEEK.value, 'revisit_within_5_weeks', 'Revisit within 5 weeks'),
    (DiscountType.REVISIT_WITHIN_6WEEK.value, 'revisit_within_6_weeks', 'Revisit within 6 weeks'),
    (DiscountType.WEEKDAY.value, 'weekday', 'Weekday')
)


class DiscountSettings(object):

    # Discount values are in [0..100] range, expressed as percentages
    weekday_discounts: Dict[Weekday, float] = {}
    first_visit_percentage: float = 0
    revisit_within_1week_percentage: float = 0
    revisit_within_2week_percentage: float = 0
    revisit_within_3week_percentage: float = 0
    revisit_within_4week_percentage: float = 0
    revisit_within_5week_percentage: float = 0
    revisit_within_6week_percentage: float = 0
    maximum_discount: float
    is_maximum_discount_enabled: float


class CalculatedPrice(object):
    price: float
    applied_discount: Optional[DiscountType]
    discount_percentage: int

    @staticmethod
    def build(
        price: float,
        applied_discount: Optional[DiscountType],
        discount_percentage: int

    ) -> 'CalculatedPrice':
        obj = CalculatedPrice()
        obj.price = price
        obj.applied_discount = applied_discount
        obj.discount_percentage = discount_percentage
        return obj


def calc_client_prices(
        stylist_timezone: tzinfo,
        discounts: DiscountSettings,
        last_visit_date: Optional[date],
        regular_price: float,
        current_demand: List[float]) -> List[CalculatedPrice]:
    """
    Calculate client prices for PRICE_BLOCK_SIZE days starting from today's date in stylists's
    timezone. For each particular day finds the maximum applicable discount. Then that
    discount is fully applied if the day's demand is minimal within all the days in the
    PRICE_BLOCK_SIZE. If the demand is higher than the minimal then the discount value
    is linearly interpolated so that zero discount corresponds to a fully booked day.
    The final applied discount is granularized, so that only some possible portions of
    discount percentage are ever used. This ensures that the prices don't jump around from
    minor demand fluctuations. See description of DISCOUNT_GRANULARIZATION for more details.

    The implemented simple heuristic approach has the following desirable characteritic:
    the discount applied is inverselly proportional to the demand, i.e. higher demand results in
    less discount and higher pricing. This is inline with our intuitive understanding of how
    the dynamic pricing should work.

    Note that the results of this function depend on the start date and block size
    (because we use minimum demand value in the block for the rest of calculations),
    that's why this function does not accept start date or block size as parameters.
    It helps ensure we always work with the same window of dates and the results are
    stable.

    Args:
        stylist_timezone: timezone of the stylist. Used to correctly determine today's date.

        discounts: the definitions of discounts for the stylist.

        last_visit_date: last time the client visited. None if they never visited (e.g.
            new client).

        regular_price: the regular price for the service.

        current_demand: A list of PRICE_BLOCK_SIZE items. Each item describes the demand for one
            day, the first item corresponds to today. The demand is a normalized number between 0
            and 1. 0 means there are no booked appointments for that day. 1 means the day is
            fully booked, no more appointments should be accepted. Usually calculated as
            (total booked time)/(total available time). normalize_demand() can be used to convert
            absolute demand values to normalized.

    Returns:
        A list of PRICE_BLOCK_SIZE items with prices. The first item represents today.

    Raises:
        ValueError exception on invalid input.
    """

    if len(current_demand) != PRICE_BLOCK_SIZE:
        raise ValueError(f"current_demand must have {PRICE_BLOCK_SIZE} elements")

    min_demand = min(current_demand)
    max_demand = max(current_demand)
    if not (0 <= min_demand <= 1 and 0 <= max_demand <= 1):
        raise ValueError("Demand values must be in [0..1] range")

    discounts_to_validate = [
        discounts.first_visit_percentage,
        discounts.revisit_within_1week_percentage,
        discounts.revisit_within_2week_percentage,
        discounts.revisit_within_3week_percentage,
        discounts.revisit_within_4week_percentage,
        discounts.revisit_within_5week_percentage,
        discounts.revisit_within_6week_percentage,
    ]

    if not all(map(is_valid_discount_percentage, discounts_to_validate)):
        raise ValueError("Invalid discount value")

    for discount in discounts.weekday_discounts.values():
        if not is_valid_discount_percentage(discount):
            raise ValueError("Invalid weekday discount value")

    results: List[CalculatedPrice] = []

    for i in range(0, PRICE_BLOCK_SIZE):
        today = datetime.now(stylist_timezone).date()
        dt = today + timedelta(days=i)
        calculated_price = CalculatedPrice()

        max_discount = find_applicable_discount(discounts, last_visit_date, dt)
        if max_discount is None:
            calculated_price.price = regular_price
            calculated_price.applied_discount = None
            calculated_price.discount_percentage = 0
        else:
            demand = current_demand[i]

            if min_demand < 1:
                # linearly interpolate the discount between 0 and max_discount
                # for demands in the range of [1 .. min_demand]. This means that
                # on the days with minimal demand full discount will be applied
                # and on the days that are fully booked zero discount will be applied
                # (actually no booking should be allowed on those days at all).
                apply_discount_part = (1 - demand) / (1 - min_demand)

                # Introduce granularity to the lienar interpolation so that the
                # the final prices fall into a few buckets instead of forming
                # a more continuous spectrum, which would be more precise but
                # undesirable from user perspective. The granularity ensures that
                # small changes in demand do not cause all prices to jump around
                # and brings some stability to them.
                apply_discount_part = granularize(apply_discount_part,
                                                  DISCOUNT_GRANULARIZATION)

                # Calculate discount percentage to apply as a portion of
                # maximum applicable discount.
                discount_percentage = (max_discount.discount_percentage *
                                       apply_discount_part)
            else:
                # The current demand is full on all days, no discount
                discount_percentage = 0

            price = regular_price * (1 - discount_percentage / 100.0)

            if discounts.is_maximum_discount_enabled and discounts.maximum_discount:
                price = max(price, (regular_price - discounts.maximum_discount))

            calculated_price.price = price

            if discount_percentage > 0:
                calculated_price.applied_discount = max_discount.type
                calculated_price.discount_percentage = round(discount_percentage)
            else:
                calculated_price.applied_discount = None
                calculated_price.discount_percentage = 0

        results.append(calculated_price)

    return results


def is_valid_discount_percentage(discount_percentage: float) -> bool:
    return 0 <= discount_percentage <= 100


def granularize(value: float, granularity: float) -> float:
    value = round(value / granularity) * granularity
    return value


class DiscountDescr(NamedTuple):
    type: DiscountType
    discount_percentage: float


def find_applicable_discount(
        discounts: DiscountSettings,
        last_visit_date: Optional[date],
        for_date: date) -> Optional[DiscountDescr]:
    """
    Return the maximum applicable discount

    Args:
        discounts: the definitions of discounts for the stylist
        last_visit_date: last time the client visited. None if they never visited (e.g. new client)
        for_date: the date to get the applicable discount for

    Returns:
        the tuple describing the type and amount of discount or None if there are no
        applicable discounts.
    """

    all_discounts: List[DiscountDescr] = []

    # Applicable weekday discount
    weekday = Weekday(for_date.isoweekday())
    weekday_discount = discounts.weekday_discounts.get(weekday)
    if weekday_discount is not None:
        discount_descr = DiscountDescr(DiscountType.WEEKDAY, weekday_discount)
        all_discounts.append(discount_descr)

    if (last_visit_date is None):
        # First time visit
        discount_descr = DiscountDescr(DiscountType.FIRST_BOOKING,
                                       discounts.first_visit_percentage)
        all_discounts.append(discount_descr)
    else:
        # Not the first time
        if last_visit_date + timedelta(weeks=1) >= for_date:
            # Within 1 week since last visit
            discount_descr = DiscountDescr(DiscountType.REVISIT_WITHIN_1WEEK,
                                           discounts.revisit_within_1week_percentage)
            all_discounts.append(discount_descr)

        elif last_visit_date + timedelta(weeks=2) >= for_date:
            # Within 2 weeks since last visit
            discount_descr = DiscountDescr(DiscountType.REVISIT_WITHIN_2WEEK,
                                           discounts.revisit_within_2week_percentage)
            all_discounts.append(discount_descr)
        elif last_visit_date + timedelta(weeks=3) >= for_date:
            # Within 3 weeks since last visit
            discount_descr = DiscountDescr(DiscountType.REVISIT_WITHIN_3WEEK,
                                           discounts.revisit_within_3week_percentage)
            all_discounts.append(discount_descr)
        elif last_visit_date + timedelta(weeks=4) >= for_date:
            # Within 4 weeks since last visit
            discount_descr = DiscountDescr(DiscountType.REVISIT_WITHIN_4WEEK,
                                           discounts.revisit_within_4week_percentage)
            all_discounts.append(discount_descr)
        elif last_visit_date + timedelta(weeks=5) >= for_date:
            # Within 5 weeks since last visit
            discount_descr = DiscountDescr(DiscountType.REVISIT_WITHIN_5WEEK,
                                           discounts.revisit_within_5week_percentage)
            all_discounts.append(discount_descr)
        elif last_visit_date + timedelta(weeks=6) >= for_date:
            # Within 6 weeks since last visit
            discount_descr = DiscountDescr(DiscountType.REVISIT_WITHIN_6WEEK,
                                           discounts.revisit_within_6week_percentage)
            all_discounts.append(discount_descr)

    max_discount = max(all_discounts, default=None, key=lambda d: d.discount_percentage)

    return max_discount


def normalize_demand(
        start_date: date,
        abs_demands: List[timedelta],
        weekday_available_hours: Dict[Weekday, timedelta]) -> List[float]:
    """
    Convert absolute demand values expressed as durations into normalized demand
    values in [0..1] range. Use to prepare demand values for calc_client_prices()
    function.

    Args:
        start_date - the date of first element in abs_demand list

        abs_demands - a list of demands, one element per day starting from start_date.
            Each element is the total duration of booked services on that date.
            The timedelta value must be positive.

        weekday_available_hours - a dictionary containing the duration that the
            stylist is available to work on a particular weekday.
            The timedelta value must be positive.

    Returns:
        A list of normalized demands, one element per day starting from start_date.


    Raises:
        ValueError exception on invalid input.
    """
    results: List[float] = []
    for i in range(0, len(abs_demands)):
        dt = start_date + timedelta(days=i)
        weekday = Weekday(dt.isoweekday())

        available: timedelta = weekday_available_hours.get(weekday, None)
        if available is None:
            normalized_demand = 1.0
        else:
            if available < timedelta(0):
                raise ValueError("weekday_available_hours must be positive timedelta values")

            try:
                demand = abs_demands[i]
                if demand < timedelta(0):
                    raise ValueError("abs_demands must be positive timedelta values")

                normalized_demand = float(demand / available)
            except ZeroDivisionError:
                normalized_demand = 1.0

        results.append(normalized_demand)

    return results
