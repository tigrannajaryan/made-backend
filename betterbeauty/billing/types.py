from core.types import StrEnum


class PaymentMethodType(StrEnum):
    CARD = 'card'


class ChargeStatus(StrEnum):
    FAILED = 'failed'
    PENDING = 'pending'
    SUCCESS = 'success'
