import logging
from typing import Optional

import stripe
from django.conf import settings
from django.db import transaction
from stripe.error import StripeError

from .models import PaymentMethod
from .types import CardRecord, PaymentMethodType

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class BillingError(Exception):

    def __init__(self, message=None, *args, **kwargs):
        self.message = message
        super(BillingError, self).__init__(*args, **kwargs)


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
