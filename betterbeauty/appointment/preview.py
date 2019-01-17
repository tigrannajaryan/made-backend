import datetime
from decimal import Decimal
from typing import Dict, List, NamedTuple, Optional
from uuid import UUID

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404

from appointment.models import Appointment, AppointmentService
from appointment.types import AppointmentStatus
from client.models import Client
from core.constants import DEFAULT_CARD_FEE, DEFAULT_TAX_RATE
from core.types import AppointmentPrices
from core.utils import calculate_appointment_prices
from salon.models import Stylist, StylistService
from salon.utils import (
    calculate_price_and_discount_for_client_on_date,
    calculate_price_with_discount_based_on_appointment,
)


class AppointmentPreviewRequest(NamedTuple):
    services: List[Dict]
    datetime_start_at: datetime.datetime
    has_tax_included: bool
    has_card_fee_included: bool
    appointment_uuid: Optional[UUID] = None


class AppointmentServicePreview(NamedTuple):
    service_name: str
    service_uuid: UUID
    client_price: Decimal
    regular_price: Decimal
    duration: datetime.timedelta
    is_original: bool
    uuid: Optional[UUID] = None


class AppointmentPreviewResponse(NamedTuple):
    grand_total: Decimal
    total_client_price_before_tax: Decimal
    total_tax: Decimal
    total_card_fee: Decimal
    duration: datetime.timedelta
    conflicts_with: QuerySet
    has_tax_included: bool
    has_card_fee_included: bool
    services: List[AppointmentServicePreview]
    stylist: Optional[Stylist]
    datetime_start_at: datetime.datetime
    status: AppointmentStatus
    total_discount_percentage: int
    total_discount_amount: Decimal
    tax_percentage: float = float(DEFAULT_TAX_RATE) * 100
    card_fee_percentage: float = float(DEFAULT_CARD_FEE) * 100


def build_appointment_preview_dict(
        stylist: Stylist,
        client: Optional[Client],
        preview_request: AppointmentPreviewRequest
) -> AppointmentPreviewResponse:
    service_items: List[AppointmentServicePreview] = []
    appointment: Optional[Appointment] = None
    status = AppointmentStatus.NEW
    if preview_request.appointment_uuid is not None:
        appointment = get_object_or_404(
            stylist.appointments,
            uuid=preview_request.appointment_uuid
        )
        status = appointment.status
    total_discount_percentage: int = 0
    if appointment:
        total_discount_percentage = appointment.total_discount_percentage
    for service_request_item in preview_request.services:
        appointment_service: Optional[AppointmentService] = None
        if appointment:
            appointment_service = appointment.services.filter(
                service_uuid=service_request_item['service_uuid']
            ).last()
        service_client_price: Optional[Decimal] = service_request_item[
            'client_price'
        ] if 'client_price' in service_request_item else None

        if appointment_service:
            if service_client_price:
                # client price (overriding current regular price) was provided. We will
                # temporarily (w/out committing to DB) replace regular price of the service
                # with client-supplied, and will re-calculate client_price (i.e. client-facing)
                # with existing appointment's discount
                appointment_service.set_client_price(service_client_price, commit=False)
            # service already exists in appointment, and will not be recalculated,
            # so we should take it's data verbatim
            service_item = AppointmentServicePreview(
                uuid=appointment_service.uuid,
                service_uuid=appointment_service.service_uuid,
                service_name=appointment_service.service_name,
                regular_price=appointment_service.regular_price,
                client_price=appointment_service.client_price,
                duration=appointment_service.duration,
                is_original=appointment_service.is_original
            )
            if not total_discount_percentage:
                total_discount_percentage = appointment_service.discount_percentage
        else:
            # appointment service doesn't exist in appointment yet, and is to be added, so we
            # need to calculate the price for it.
            service: StylistService = stylist.services.get(
                uuid=service_request_item['service_uuid']
            )
            # We need to decide what we use for the base price. If client_price is supplied
            # we will use it as a base price. Otherwise, we will take base price from stylist's
            # service
            if not service_client_price:
                regular_price = service.regular_price
            else:
                regular_price = service_client_price
            # now when we know the base price, we need to calculate price with discount.
            # if the appointment we're previewing is based on the existing appointment -
            # we will just take discount percentage from it. Otherwise, we need to run
            # pricing calculation for given client and stylist on the given date, and see
            # if there is any discount there
            if not appointment:
                calculated_price = calculate_price_and_discount_for_client_on_date(
                    service=service, client=client,
                    date=preview_request.datetime_start_at.date()
                )
                client_price = Decimal(calculated_price.price)
                if not total_discount_percentage:
                    total_discount_percentage = calculated_price.discount_percentage
            else:
                client_price = calculate_price_with_discount_based_on_appointment(
                    regular_price, appointment
                )

            service_item = AppointmentServicePreview(
                uuid=None,
                service_uuid=service.uuid,
                service_name=service.name,
                regular_price=service.regular_price,
                client_price=client_price,
                duration=service.duration,
                is_original=True if not appointment else False
            )
        service_items.append(service_item)

    total_client_price_before_tax = sum([s.client_price for s in service_items], Decimal(0))
    total_regular_price = sum([s.regular_price for s in service_items], Decimal(0))
    appointment_prices: AppointmentPrices = calculate_appointment_prices(
        price_before_tax=total_client_price_before_tax,
        include_card_fee=preview_request.has_card_fee_included,
        include_tax=preview_request.has_tax_included
    )
    duration = stylist.service_time_gap

    conflicts_with = stylist.get_appointments_in_datetime_range(
        preview_request.datetime_start_at,
        preview_request.datetime_start_at,
        including_to=True,
        exclude_statuses=[
            AppointmentStatus.CANCELLED_BY_STYLIST,
            AppointmentStatus.CANCELLED_BY_CLIENT
        ]
    )
    return AppointmentPreviewResponse(
        duration=duration,
        conflicts_with=conflicts_with,
        total_client_price_before_tax=appointment_prices.total_client_price_before_tax,
        grand_total=appointment_prices.grand_total,
        tax_percentage=float(DEFAULT_TAX_RATE) * 100,
        card_fee_percentage=float(DEFAULT_CARD_FEE) * 100,
        total_tax=appointment_prices.total_tax,
        total_card_fee=appointment_prices.total_card_fee,
        has_tax_included=appointment_prices.has_tax_included,
        has_card_fee_included=appointment_prices.has_card_fee_included,
        services=service_items,
        stylist=stylist,
        datetime_start_at=preview_request.datetime_start_at,
        status=status,
        total_discount_percentage=total_discount_percentage,
        total_discount_amount=max(
            total_regular_price - total_client_price_before_tax, Decimal(0)
        )
    )
