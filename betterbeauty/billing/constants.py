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


class ErrorMessages(object):
    ERR_UNRECOVERABLE_BILLING_ERROR = 'err_unrecoverable_billing_error'
    ERR_ACTIONABLE_BILLING_ERROR_WITH_MESSAGE = 'err_actionable_billing_error_with_message'
    ERR_CANNOT_CHECKOUT_WITHOUT_CLIENT = 'err_cannot_checkout_without_client'
    ERR_BAD_PAYMENT_METHOD = 'err_bad_payment_method'
