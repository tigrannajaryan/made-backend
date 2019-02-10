from uuid import uuid4

from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
from django.utils import timezone

from stripe.error import CardError, StripeError, StripeErrorWithParamCode

from .constants import ChargeStatusChoices, PaymentMethodChoices
from .types import ChargeStatus, PaymentMethodType


class PaymentMethod(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    client = models.ForeignKey(
        'client.Client', on_delete=models.CASCADE, related_name='payment_methods'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField()
    stripe_id = models.CharField(max_length=64)
    type = models.CharField(
        max_length=16, choices=PaymentMethodChoices, default=PaymentMethodType.CARD
    )
    card_brand = models.CharField(max_length=16)
    expiry_month = models.PositiveIntegerField()
    expiry_year = models.PositiveIntegerField()
    last_four_digits = models.CharField(max_length=4)

    class Meta:
        db_table = 'payment_method'

    def __str__(self):
        return '[{0}] {1} (** {3}), {2}'.format(
            'Active' if self.is_active else 'Inactive',
            self.card_brand.upper(),
            self.client.get_full_name(),
            self.last_four_digits
        )

    @transaction.atomic()
    def set_active(self):
        """Set current payment method active, and deactivate other active methods if any"""
        self.client.payment_methods.filter(is_active=True).exclude(id=self.id).update(
            is_active=False
        )
        self.is_active = True
        self.save(update_fields=['is_active', ])


class Charge(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    client = models.ForeignKey('client.Client', on_delete=models.CASCADE)
    payment_method = models.ForeignKey(PaymentMethod, null=True, on_delete=models.SET_NULL)
    appointment = models.ForeignKey(
        'appointment.Appointment', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='charges'
    )
    amount = models.DecimalField(max_digits=6, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    charged_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=16, choices=ChargeStatusChoices, default=ChargeStatus.PENDING
    )
    stripe_id = models.CharField(max_length=64)
    error_data = JSONField(null=True, blank=True, default=dict)

    class Meta:
        db_table = 'charge'

    def __str__(self):
        return '[{0}] ${1} from {2} for {3}'.format(
            self.status.upper(),
            self.amount,
            self.client.get_full_name(),
            self.appointment
        )

    @transaction.atomic
    def run_stripe_charge(self) -> ChargeStatus:
        # we should only allow running charges once
        if self.status != ChargeStatus.PENDING or self.stripe_id:
            return self.status
        from .utils import format_stripe_error_data, run_charge
        try:
            charge_id = run_charge(
                self.client.stripe_id,
                amount=self.amount,
                description=self.description,
                payment_method_stripe_id=self.payment_method.stripe_id
            )
            if charge_id:
                self.stripe_id = charge_id
                self.status = ChargeStatus.SUCCESS
                self.charged_at = timezone.now()
                self.save(update_fields=['stripe_id', 'status', 'charged_at', ])
                return ChargeStatus.SUCCESS
        except (CardError, StripeError, StripeErrorWithParamCode) as error:
            self.status = ChargeStatus.FAILED
            self.error_data = format_stripe_error_data(error)
            self.save(update_fields=['status', 'error_data'])
            raise
        return ChargeStatus.FAILED
