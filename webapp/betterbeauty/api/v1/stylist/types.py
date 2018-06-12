import datetime
from decimal import Decimal

from typing import Dict, List, NamedTuple, Optional
from uuid import UUID

from django.db.models import QuerySet


class AppointmentPreviewRequest(NamedTuple):
    services: List[Dict]
    datetime_start_at: datetime.datetime
    has_tax_included: bool
    has_card_fee_included: bool
    client_uuid: Optional[UUID] = None


class AppointmentPreviewResponse(NamedTuple):
    grand_total: Decimal
    total_client_price_before_tax: Decimal
    total_tax: Decimal
    total_card_fee: Decimal
    duration: datetime.timedelta
    conflicts_with: QuerySet
    has_tax_included: bool
    has_card_fee_included: bool
