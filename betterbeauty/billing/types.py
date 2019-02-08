from typing import NamedTuple

from core.types import StrEnum


class PaymentMethodType(StrEnum):
    CARD = 'card'


class ChargeStatus(StrEnum):
    FAILED = 'failed'
    PENDING = 'pending'
    SUCCESS = 'success'


class CardRecord(NamedTuple):
    last_four_digits: str
    expiry_year: int
    expiry_month: int
    stripe_id: str
    card_brand: str
