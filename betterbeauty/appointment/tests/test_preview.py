import datetime

import mock
import pytest
import pytz

from django.http.response import Http404
from django_dynamic_fixture import G

from appointment.models import Appointment, AppointmentService
from appointment.preview import (
    AppointmentPreviewRequest,
    AppointmentPreviewResponse,
    AppointmentServicePreview,
    build_appointment_preview_dict,
)
from appointment.types import AppointmentStatus
# from client.models import Client, ClientOfStylist
from pricing import CalculatedPrice
from salon.models import Stylist, StylistService


class TestBuildAppointmentPreviewDict(object):

    @pytest.mark.django_db
    def test_bad_appointment_uuid(self):
        stylist = G(Stylist)
        appointment = G(
            Appointment, datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC)
        )
        preview_request = AppointmentPreviewRequest(
            services=[],
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            has_tax_included=False,
            has_card_fee_included=False,
            appointment_uuid=appointment.uuid
        )
        with pytest.raises(Http404):
            build_appointment_preview_dict(
                stylist=stylist,
                client_of_stylist=None,
                preview_request=preview_request
            )

    @pytest.mark.django_db
    def test_without_services(self):
        stylist: Stylist = G(Stylist)
        preview_request = AppointmentPreviewRequest(
            services=[],
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            has_tax_included=False,
            has_card_fee_included=False,
        )
        preview_dict = build_appointment_preview_dict(
            stylist=stylist,
            client_of_stylist=None,
            preview_request=preview_request
        )
        assert(preview_dict.conflicts_with.count() == 0)
        # we can't compare QuerySets, so will just replace the field
        preview_dict = preview_dict._replace(conflicts_with=None)
        assert(preview_dict == AppointmentPreviewResponse(
            grand_total=0,
            total_client_price_before_tax=0,
            total_tax=0,
            total_card_fee=0,
            duration=stylist.service_time_gap,
            conflicts_with=None,
            has_tax_included=False,
            has_card_fee_included=False,
            services=[],
            stylist=stylist,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            status=AppointmentStatus.NEW
        ))

    @pytest.mark.django_db
    @mock.patch(
        'appointment.preview.calculate_price_and_discount_for_client_on_date',
        lambda service, client, date: CalculatedPrice.build(0, None, 0)
    )
    def test_without_existing_appointment_with_new_services(self):
        stylist: Stylist = G(Stylist)
        service: StylistService = G(StylistService, stylist=stylist)
        preview_request = AppointmentPreviewRequest(
            services=[
                {'service_uuid': service.uuid}
            ],
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            has_tax_included=False,
            has_card_fee_included=False,
        )
        preview_dict = build_appointment_preview_dict(
            stylist=stylist,
            client_of_stylist=None,
            preview_request=preview_request
        )
        assert (preview_dict.conflicts_with.count() == 0)
        # we can't compare QuerySets, so will just replace the field
        preview_dict = preview_dict._replace(conflicts_with=None)
        assert (preview_dict == AppointmentPreviewResponse(
            grand_total=0,
            total_client_price_before_tax=0,
            total_tax=0,
            total_card_fee=0,
            duration=stylist.service_time_gap,
            conflicts_with=None,
            has_tax_included=False,
            has_card_fee_included=False,
            services=[
                AppointmentServicePreview(
                    service_name=service.name,
                    service_uuid=service.uuid,
                    client_price=0,
                    regular_price=service.regular_price,
                    duration=service.duration,
                    is_original=True,
                    uuid=None,
                ),
            ],
            stylist=stylist,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            status=AppointmentStatus.NEW
        ))

    @pytest.mark.django_db
    @pytest.mark.django_db
    @mock.patch(
        'appointment.preview.calculate_price_and_discount_for_client_on_date',
        lambda service, client, date: CalculatedPrice.build(0, None, 0)
    )
    def test_with_existing_appointment_with_new_services(self):
        stylist: Stylist = G(Stylist)
        existing_service: StylistService = G(
            StylistService, stylist=stylist, regular_price=0
        )
        service: StylistService = G(
            StylistService, stylist=stylist, regular_price=0
        )
        appointment: Appointment = G(
            Appointment, stylist=stylist,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC)
        )
        appointment_service: AppointmentService = G(
            AppointmentService,
            appointment=appointment,
            service_uuid=existing_service.uuid,
            is_original=True,
            service_name=existing_service.name,
            regular_price=0,
            calculated_price=0,
            client_price=0
        )
        preview_request = AppointmentPreviewRequest(
            services=[
                {'service_uuid': service.uuid},
                {'service_uuid': existing_service.uuid},
            ],
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            has_tax_included=False,
            has_card_fee_included=False,
            appointment_uuid=appointment.uuid
        )
        preview_dict = build_appointment_preview_dict(
            stylist=stylist,
            client_of_stylist=None,
            preview_request=preview_request
        )
        assert (preview_dict.conflicts_with.count() == 0)
        # we can't compare QuerySets, so will just replace the field
        preview_dict = preview_dict._replace(conflicts_with=None)
        assert (preview_dict == AppointmentPreviewResponse(
            grand_total=0,
            total_client_price_before_tax=0,
            total_tax=0,
            total_card_fee=0,
            duration=stylist.service_time_gap,
            conflicts_with=None,
            has_tax_included=False,
            has_card_fee_included=False,
            services=[
                AppointmentServicePreview(
                    service_name=service.name,
                    service_uuid=service.uuid,
                    client_price=0,
                    regular_price=service.regular_price,
                    duration=service.duration,
                    is_original=False,
                    uuid=None,
                ),
                AppointmentServicePreview(
                    service_name=existing_service.name,
                    service_uuid=existing_service.uuid,
                    client_price=0,
                    regular_price=existing_service.regular_price,
                    duration=existing_service.duration,
                    is_original=True,
                    uuid=appointment_service.uuid,
                ),
            ],
            stylist=stylist,
            datetime_start_at=datetime.datetime(2018, 1, 1, 0, 0, tzinfo=pytz.UTC),
            status=appointment.status
        ))
