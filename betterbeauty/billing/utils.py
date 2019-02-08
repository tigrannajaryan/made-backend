import logging
from decimal import Decimal
from typing import Optional, Union

import stripe
from django.conf import settings
from django.db import transaction
from stripe.error import CardError, StripeError, StripeErrorWithParamCode

from .models import PaymentMethod
from .types import CardRecord, PaymentMethodType

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


def format_stripe_error_data(
        error: Union[StripeError, StripeErrorWithParamCode, CardError]
) -> dict:
    """Format stripe exception into serializable dict. INH."""
    data = {
        'error_class': error.__class__.__name__,
    }
    if hasattr(error, 'message'):
        data['message'] = error.message
    else:
        data['message'] = getattr(error, '_message', 'Unknown error.')

    http_status = getattr(error, 'http_status', None)
    if http_status is not None:
        data['http_status'] = http_status
    param = getattr(error, 'param', None)
    if param is not None:
        data['param'] = param
    if isinstance(error, CardError):
        data['code'] = getattr(error, 'code', None)
        if error.json_body and 'error' in error.json_body:
            data['error'] = error.json_body['error']
    return data


def create_stripe_customer_for_client(client, token: str) -> str:
    """Register client with stripe and return stripe id"""
    stripe_customer = stripe.Customer.create(
        card=token,
        description=client.get_full_name(),
        email=client.email,
        metadata={
            'phone': client.user.phone
        }
    )
    return stripe_customer.id


def retrieve_default_card_details(stripe_customer_id) -> Optional[CardRecord]:
    """Return dict populated with default card data based on stripe customer_id string"""
    try:
        stripe_customer = stripe.Customer.retrieve(stripe_customer_id)
        cards_list = stripe_customer.sources.list(object='card')['data']
        if not cards_list:
            return None
        default_card = CardRecord(
            stripe_id=cards_list[0]['id'],
            last_four_digits=cards_list[0]['last4'],
            expiry_year=int(cards_list[0]['exp_year']),
            expiry_month=int(cards_list[0]['exp_month']),
            card_brand=cards_list[0]['brand'].lower()
        )
        return default_card
    except (IndexError, KeyError):
        return None
    except StripeError as err:
        logger.exception(
            'Could not retrieve card details for client with '
            'stripe_id = {0}; message was: {1}'.format(
                stripe_customer_id,
                err.message
            ))
        return None


@transaction.atomic
def create_new_payment_method(client, stripe_token) -> Optional[PaymentMethod]:
    """Create (or replace) new payment method for existing client"""
    if not client.stripe_id:
        # there's no Stripe record for this client yet. Firstly, we'll create
        # the customer record in Stripe and will save it to client object. Because
        # we're creating stripe customer record with a token from credit card addition,
        # it will automatically create 2 Stripe objects - customer and card, already
        # connected on Stripe's side, so no extra call to add new Source (i.e. card)
        # is required
        stripe_customer_id = create_stripe_customer_for_client(client, stripe_token)
        client.stripe_id = stripe_customer_id
        client.save(update_fields=['stripe_id', ])
    else:
        # Stripe customer exists, so we need to add new Source object from token
        stripe_customer = stripe.Customer.retrieve(client.stripe_id)
        # The code below *replaces* the default payment source. Down the road, when
        # we want to support multiple payment methods (e.g. multiple cards or other
        # payment sources) we'll need to change this code to
        #
        # new_payment_method = stripe_customer.sources.create(source=card_token)
        #
        # and then use the id of the freshly added payment method to create
        # the PaymentMethod DB object.
        stripe_customer.source = stripe_token
        stripe_customer.save()
    # We've added the card, and now client is registered with Stripe. Now we need
    # to make a second query to actually retrieve the default payment method details
    # and save it to our DB
    stripe_customer_id = client.stripe_id
    card_data: Optional[CardRecord] = retrieve_default_card_details(stripe_customer_id)
    if not card_data:
        return None
    payment_method: PaymentMethod = PaymentMethod.objects.create(
        client=client,
        is_active=False,
        type=PaymentMethodType.CARD,
        **card_data._asdict()
    )
    # Now we need to set the newly added payment method as active, and simultaneously
    # de-activate other methods
    payment_method.set_active()
    return payment_method


def run_charge(
        customer_stripe_id: str,
        amount: Decimal,
        description: str,
        payment_method_stripe_id: Optional[str] = None,
) -> Optional[str]:
    """
    Creates actual Stripe charge, and attepmts to charge client

    :param customer_stripe_id: customer stripe id of the client
    :param payment_method_stripe_id: stripe id of payment method, must be attached to customer.
    If it omitted, charge will be made using the default payment method
    :param amount: charge amount in USD
    :param description: description of the charge, how it will show in client's bank statement
    :return: stripe id of the charge if successful, None otherwise
    """
    if amount <= 0.0:
        logger.warning(
            'Could not create charge for client with '
            'stripe_id == {0} with non-positive amount'.format(
                customer_stripe_id
            ))
        return None
    charge_data = {
        'amount': int(amount * 100),
        'currency': settings.STRIPE_DEFAULT_CURRENCY,
        'customer': customer_stripe_id,
        'description': description,
        'statement_descriptor': settings.STRIPE_DEFAULT_PAYMENT_DESCRIPTOR
    }
    if payment_method_stripe_id is not None:
        charge_data['source'] = payment_method_stripe_id
    charge = stripe.Charge.create(**charge_data)
    logger.info('Created ${0} charge for client with stripe_id == {1}'.format(
        amount,
        customer_stripe_id
    ))
    return charge.id
