from model_utils import Choices

from .types import ChargeStatus, PaymentMethodType

PaymentMethodChoices = Choices(
    (PaymentMethodType.CARD, 'card', 'card'),
)

ChargeStatusChoices = Choices(
    (ChargeStatus.FAILED, 'failed', 'Failed'),
    (ChargeStatus.PENDING, 'pending', 'Pending'),
    (ChargeStatus.SUCCESS, 'success', 'Success'),
)
