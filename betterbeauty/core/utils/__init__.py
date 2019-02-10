from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from ..types import AppointmentPrices


def post_or_get(request, key, default=None):
    return request.POST.get(key, request.GET.get(key, default))


def post_or_get_or_data(request, key, default=None):
    return request.POST.get(key, request.GET.get(key, (
        request.data.get(key, default) if isinstance(request.data, dict) else default
    )))


def calculate_tax(original_cost: Decimal, tax_rate: Decimal) -> Decimal:
    return original_cost * Decimal(tax_rate)


def calculate_card_fee(original_cost: Decimal, card_fee: Decimal) -> Decimal:
    return original_cost * Decimal(card_fee)


def calculate_stripe_card_fee(original_cost: Decimal) -> Decimal:
    # Return Stripe transaction fee - 2.9%  + 30 cents
    return Decimal(
        original_cost * Decimal(0.029) + Decimal(0.3)
    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculate_stylist_payout_amount(original_cost: Decimal, is_stripe_payment: bool) -> Decimal:
    if not is_stripe_payment:
        return original_cost
    return original_cost - calculate_stripe_card_fee(original_cost)


def calculate_appointment_prices(
        price_before_tax: Decimal,
        include_card_fee: bool,
        include_tax: bool,
        tax_rate: Decimal,
        card_fee: Decimal,
        is_stripe_payment: Optional[bool] = False
) -> AppointmentPrices:
    grand_total: Decimal = price_before_tax
    # HOTFIX: if grand_total is passed as int or float - cast it
    # explicitly to Decimal
    if not isinstance(grand_total, Decimal):
        grand_total = Decimal(grand_total)
    total_tax: Decimal = calculate_tax(price_before_tax, tax_rate)
    if include_tax:
        grand_total += total_tax
    total_card_fee: Decimal = calculate_card_fee(grand_total, card_fee)
    if include_card_fee:
        grand_total += total_card_fee
    grand_total = grand_total.quantize(Decimal('1.'), rounding=ROUND_HALF_UP)
    stylist_payout_amount = calculate_stylist_payout_amount(
        grand_total, is_stripe_payment=is_stripe_payment
    )
    return AppointmentPrices(
        total_client_price_before_tax=price_before_tax,
        total_tax=total_tax,
        total_card_fee=total_card_fee,
        grand_total=grand_total,
        has_tax_included=include_tax,
        has_card_fee_included=include_card_fee,
        stylist_payout_amount=stylist_payout_amount
    )
