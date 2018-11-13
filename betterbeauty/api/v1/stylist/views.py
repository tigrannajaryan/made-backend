import datetime
import uuid
from typing import List, NamedTuple, Optional

from annoying.functions import get_object_or_None
from dateutil.parser import parse
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from django.db import models, transaction
from django.db.models import Case, IntegerField, Q, Value, When

from rest_framework import generics, permissions, status, views
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from api.common.permissions import (
    StylistPermission,
    StylistRegisterUpdatePermission,
)
from appointment.models import Appointment
from appointment.preview import (
    AppointmentPreviewRequest,
    build_appointment_preview_dict,
)
from appointment.types import AppointmentStatus
from client.models import Client
from core.utils import (
    post_or_get,
)
from salon.models import ServiceTemplateSet, Stylist, StylistAvailableWeekDay, StylistService
from salon.types import ClientPriceOnDate
from salon.utils import (
    generate_client_prices_for_stylist_services,
    get_default_service_uuids)
from .constants import ErrorMessages, MAX_APPOINTMENTS_PER_REQUEST, NEARBY_CLIENTS_ACCURACY
from .serializers import (
    AppointmentPreviewRequestSerializer,
    AppointmentPreviewResponseSerializer,
    AppointmentSerializer,
    AppointmentsOnADaySerializer,
    AppointmentUpdateSerializer,
    ClientDetailsSerializer,
    ClientSerializer,
    ClientServicePricingSerializer,
    InvitationSerializer,
    MaximumDiscountSerializer,
    NearbyClientSerializer,
    ServiceTemplateSetDetailsSerializer,
    ServiceTemplateSetListSerializer,
    StylistAvailableWeekDayListSerializer,
    StylistAvailableWeekDaySerializer,
    StylistDiscountsSerializer,
    StylistHomeSerializer,
    StylistSerializer,
    StylistSerializerWithGoogleAPIKey,
    StylistServiceListSerializer,
    StylistServicePricingRequestSerializer,
    StylistServicePricingSerializer,
    StylistServiceSerializer,
    StylistSettingsRetrieveSerializer,
    StylistTodaySerializer,
)


class ClientPricingRequest(NamedTuple):
    client_uuid: Optional[uuid.UUID]
    service_uuids: List[uuid.UUID] = []


class ClientPricingResponse(NamedTuple):
    prices: List[ClientPriceOnDate]
    client_uuid: Optional[uuid.UUID]
    service_uuids: List[uuid.UUID] = []


class StylistView(
    generics.CreateAPIView, generics.RetrieveUpdateAPIView
):
    serializer_class = StylistSerializer
    permission_classes = [StylistRegisterUpdatePermission, permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return StylistSerializerWithGoogleAPIKey
        return super(StylistView, self).get_serializer_class()

    def get_object(self):
        return get_object_or_None(
            Stylist,
            user=self.request.user
        )

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }


class ServiceTemplateSetListView(views.APIView):
    serializer_class = ServiceTemplateSetListSerializer
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                'service_template_sets': self.serializer_class(self.get_queryset(), many=True).data
            }
        )

    def get_queryset(self):
        return ServiceTemplateSet.objects.all().order_by('sort_weight')


class ServiceTemplateSetDetailsView(generics.RetrieveAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = ServiceTemplateSetDetailsSerializer
    lookup_field = 'uuid'
    lookup_url_kwarg = 'template_set_uuid'

    def get_queryset(self):
        return ServiceTemplateSet.objects.all()

    def get_serializer_context(self):
        return {'stylist': self.request.user.stylist}


class StylistServiceListView(generics.RetrieveUpdateAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = StylistServiceListSerializer

    def post(self, request, *args, **kwargs):
        """Use this merely to allow using POST as PATCH"""
        return self.partial_update(request, *args, **kwargs)

    def get_object(self):
        return self.request.user.stylist

    def get_queryset(self):
        return self.request.user.stylist.services.all()


class StylistServiceView(generics.DestroyAPIView):
    serializer_class = StylistServiceSerializer
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    lookup_url_kwarg = 'uuid'
    lookup_field = 'uuid'

    def delete(self, request, *args, **kwargs):
        service: StylistService = self.get_object()
        service.deleted_at = service.stylist.get_current_now()
        service.save(update_fields=['deleted_at', ])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        return self.request.user.stylist.services.all()


class StylistAvailabilityView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get(self, request):
        return Response(StylistAvailableWeekDayListSerializer(self.get_object()).data)

    def patch(self, request):
        return self.post(request)

    def post(self, request):
        serializer = StylistAvailableWeekDaySerializer(
            data=request.data, many=True,
            context={'user': self.request.user}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(stylist=self.get_object())
        return Response(
            StylistAvailableWeekDayListSerializer(self.get_object()).data
        )

    def get_object(self):
        return getattr(self.request.user, 'stylist', None)


class StylistDiscountsView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = StylistDiscountsSerializer

    def get(self, request):
        return Response(StylistDiscountsSerializer(self.get_object()).data)

    def patch(self, request, *args, **kwargs):
        serializer = StylistDiscountsSerializer(
            instance=self.request.user.stylist,
            data=request.data,
            context={'user': self.request.user},
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(StylistDiscountsSerializer(self.get_object()).data)

    def post(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)

    def get_object(self):
        return getattr(self.request.user, 'stylist', None)


class StylistTodayView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get(self, request):
        return Response(StylistTodaySerializer(self.get_object()).data)

    def get_object(self):
        return getattr(self.request.user, 'stylist', None)


class StylistMaximumDiscountView(generics.RetrieveUpdateAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = MaximumDiscountSerializer

    def get(self, request, *args, **kwargs):
        return Response(MaximumDiscountSerializer(self.get_object()).data)

    def post(self, request, *args, **kwargs):
        return self.update(request, args, kwargs)

    def get_object(self):
        return getattr(self.request.user, 'stylist', None)


class StylistHomeView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params['query']
        serializer = StylistHomeSerializer(self.get_object(),
                                           context={'query': query},
                                           data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)

    def get_object(self):
        return getattr(self.request.user, 'stylist', None)


class StylistAppointmentListCreateView(generics.ListCreateAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer

    def get_serializer_context(self):
        return {
            'stylist': self.request.user.stylist,
            'force_start': post_or_get(self.request, 'force_start', False) == 'true'
        }

    def get_queryset(self):
        stylist = self.request.user.stylist

        date_from_str = post_or_get(self.request, 'date_from')
        date_to_str = post_or_get(self.request, 'date_to')

        exclude_statuses = None
        if post_or_get(self.request, 'include_cancelled', False) == 'true':
            exclude_statuses = [
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST
            ]
        limit = int(post_or_get(self.request, 'limit', MAX_APPOINTMENTS_PER_REQUEST))

        datetime_from = None
        datetime_to = None

        if date_from_str:
            datetime_from = parse(date_from_str).replace(
                hour=0, minute=0, second=0
            )
        if date_to_str:
            datetime_to = (parse(date_to_str) + datetime.timedelta(days=1)).replace(
                hour=0, minute=0, second=0
            )
        return stylist.get_appointments_in_datetime_range(
            datetime_from, datetime_to,
            exclude_statuses=exclude_statuses
        )[:limit]


class AppointmentsOnADayView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get(self, request):
        stylist: Stylist = self.request.user.stylist
        date_str = post_or_get(request, 'date', None)
        if date_str:
            date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            date = stylist.get_current_now().date()
        appointments: models.QuerySet = stylist.get_appointments_in_datetime_range(
            datetime_from=datetime.datetime.combine(date, datetime.datetime.min.time(),
                                                    tzinfo=stylist.salon.timezone),
            datetime_to=datetime.datetime.combine(date, datetime.datetime.max.time(),
                                                  tzinfo=stylist.salon.timezone),
            exclude_statuses=[AppointmentStatus.CANCELLED_BY_STYLIST],
            including_to=True
        ).order_by('datetime_start_at')
        available_weekday: StylistAvailableWeekDay = stylist.available_days.get(
            weekday=date.isoweekday(),
        )
        response_serializer = AppointmentsOnADaySerializer(
            {}, context={
                'stylist': stylist,
                'appointments': appointments,
                'available_weekday': available_weekday
            }
        )
        return Response(response_serializer.data)


class StylistAppointmentPreviewView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def post(self, request):
        stylist: Stylist = self.request.user.stylist
        try:
            appointment: Appointment = stylist.appointments.get(
                uuid=request.data['appointment_uuid'])
        except Appointment.DoesNotExist:
            raise ValidationError(
                {'non_field_errors': [{'code': ErrorMessages.ERR_INVALID_APPOINTMENT_UUID}]})
        serializer = AppointmentPreviewRequestSerializer(
            data=request.data, context={'stylist': stylist,
                                        'appointment': appointment, 'force_start': True}
        )
        serializer.is_valid(raise_exception=True)
        client_uuid = serializer.validated_data.pop('client_uuid', None)
        client: Optional[Client] = None
        if client_uuid:
            client = stylist.get_preferred_clients().get(
                uuid=client_uuid
            )
        preview_request = AppointmentPreviewRequest(**serializer.validated_data)
        response_serializer = AppointmentPreviewResponseSerializer(
            build_appointment_preview_dict(
                stylist=stylist,
                client=client,
                preview_request=preview_request
            )
        )
        return Response(response_serializer.data)


class StylistAppointmentRetrieveUpdateCancelView(
    generics.RetrieveUpdateDestroyAPIView
):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    lookup_url_kwarg = 'appointment_uuid'
    lookup_field = 'uuid'

    def post(self, request, *args, **kwargs):
        """Use this merely to allow using POST as PATCH"""
        return self.partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance: Appointment):
        instance.set_status(AppointmentStatus.CANCELLED_BY_STYLIST, self.request.user)

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return AppointmentSerializer
        return AppointmentUpdateSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        appointment = serializer.save()
        return Response(AppointmentSerializer(appointment).data)

    def get_serializer_context(self):
        stylist = self.request.user.stylist
        appointment: Appointment = stylist.appointments.get(
            uuid=self.kwargs['appointment_uuid'])
        return {
            'user': self.request.user,
            'stylist': self.request.user.stylist,
            'appointment': appointment
        }

    def get_queryset(self):
        stylist = self.request.user.stylist
        return Appointment.all_objects.filter(
            stylist=stylist
        ).order_by('datetime_start_at')


class InvitationView(generics.ListCreateAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = InvitationSerializer

    def get(self, request, *args, **kwargs):
        return Response({'invitations': self.get_serializer(
            self.get_queryset(), many=True
        ).data})

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        stylist = self.request.user.stylist
        with transaction.atomic():
            created_objects = serializer.save(stylist=stylist)
            stylist.has_invited_clients = True
            stylist.save(update_fields=['has_invited_clients'])
        response_status = status.HTTP_200_OK
        if len(created_objects) > 0:
            response_status = status.HTTP_201_CREATED
        return Response({'invitations':
                        self.serializer_class(created_objects, many=True).data
                         }, status=response_status)

    def get_queryset(self):
        stylist: Stylist = self.request.user.stylist
        return stylist.invites.all()


class StylistSettingsRetrieveView(generics.RetrieveAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = StylistSettingsRetrieveSerializer

    def get_object(self):
        return self.request.user.stylist


class StylistServicePricingView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        stylist = request.user.stylist
        serializer = StylistServicePricingRequestSerializer(
            data=request.data, context={'stylist': request.user.stylist}
        )
        serializer.is_valid(raise_exception=True)
        client_uuid = serializer.validated_data.get('client_uuid', None)
        client: Optional[Client] = None
        if client_uuid:
            client = get_object_or_None(
                stylist.get_preferred_clients(),
                uuid=client_uuid
            )
        service_uuid = serializer.validated_data['service_uuid']

        service = self.get_queryset().filter(uuid=service_uuid).last()

        return Response(
            StylistServicePricingSerializer(
                service, context={'client': client}
            ).data
        )

    def get_queryset(self):
        return self.request.user.stylist.services.all()


class ClientListView(generics.ListAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = ClientSerializer

    def get(self, request, *args, **kwargs):
        serializer = ClientSerializer(self.get_queryset(),
                                      many=True, context=self.get_serializer_context())
        response_dict = {
            'clients': serializer.data
        }
        return Response(response_dict, status=status.HTTP_200_OK)

    def get_queryset(self):
        stylist: Stylist = self.request.user.stylist
        queryset = stylist.get_preferred_clients()
        return queryset

    def get_serializer_context(self):
        return {'stylist': self.request.user.stylist}


class ClientView(generics.RetrieveAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = ClientDetailsSerializer

    lookup_field = 'uuid'
    lookup_url_kwarg = 'client_uuid'

    def get_queryset(self):
        stylist: Stylist = self.request.user.stylist
        queryset = stylist.get_preferred_clients()
        return queryset

    def get_serializer_context(self):
        return {'stylist': self.request.user.stylist}


class NearbyClientsView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = NearbyClientSerializer(self.get_queryset(), many=True)
        response_dict = {
            'clients': serializer.data
        }
        return Response(response_dict, status=status.HTTP_200_OK)

    def get_queryset(self):
        salon = self.request.user.stylist.salon
        if salon:
            location = salon.location
            if location:
                return NearbyClientsView._search_clients(
                    location=location, country=salon.country)

        raise ValidationError(
            {'non_field_errors': [{'code': ErrorMessages.ERR_STYLIST_LOCATION_UNAVAILABLE}]})

    @staticmethod
    def _search_clients(location: Point, country: str) -> models.QuerySet:
        """
        Ordering
        ========
        We are ordering clients by profile_completeness and then by distance

        Profile completeness ranking is calculated in the following order
         1. Has first name, has photo
         2. Has first name, no photo
         3. No first name, has photo
         4. No first name, No photo
        """
        queryset = Client.objects.filter(country__iexact=country)

        nearby_clients = NearbyClientsView._get_nearby_clients(queryset, location)

        queryset = nearby_clients.annotate(profile_completeness=Case(
            When((Q(user__first_name='', user__photo='')), then=Value(4)),
            When((Q(user__first_name='') & ~Q(user__photo='')), then=Value(3)),
            When(Q(user__first_name__isnull=False, user__photo=''), then=Value(2)),
            When(Q(user__first_name__isnull=False) & ~Q(user__photo=''), then=Value(1)),
            output_field=IntegerField(),
        )).order_by('profile_completeness', 'distance')[:1000]

        return queryset

    @staticmethod
    def _get_nearby_clients(queryset: models.QuerySet,
                            location: Point) -> models.QuerySet:
        """
        Filter conditions
        =================
        Has no zip code
        Attempted to geocode invalid zip-code
        Has latitude and longitude which and is within NEARBY_CLIENTS_ACCURACY.

        """
        queryset = queryset.filter(Q(zip_code__isnull=True) | Q(
            last_geo_coded__isnull=False) | Q(
            location__distance_lte=(location, D(m=NEARBY_CLIENTS_ACCURACY)))).annotate(
            distance=Distance('location', location))
        return queryset


class ClientPricingView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def post(self, request):
        stylist: Stylist = self.request.user.stylist
        serializer = ClientServicePricingSerializer(
            context={'stylist': stylist}, data=request.data
        )
        serializer.is_valid(raise_exception=True)
        request_data = ClientPricingRequest(**serializer.validated_data)
        client: Optional[Client] = None
        client_uuid = request_data.client_uuid
        if client_uuid:
            client = stylist.get_preferred_clients().get(uuid=client_uuid)
        service_uuids = request_data.service_uuids

        pricing_response = self._get_pricing_response(
            stylist=stylist, client=client, service_uuids=service_uuids
        )

        return Response(
            ClientServicePricingSerializer(pricing_response).data
        )

    @staticmethod
    def _get_pricing_response(
            stylist: Stylist, client: Optional[Client],
            service_uuids: Optional[List[uuid.UUID]] = None
    ) -> ClientPricingResponse:

        if service_uuids is None or not service_uuids:
            service_uuids = get_default_service_uuids(
                stylist=stylist, client=client
            )

        services = [stylist.services.get(uuid=uuid) for uuid in service_uuids]

        prices = generate_client_prices_for_stylist_services(
            stylist=stylist,
            services=services,
            client=client,
            exclude_fully_booked=False,
            exclude_unavailable_days=False
        )
        pricing_response = ClientPricingResponse(
            client_uuid=client.uuid if client else None,
            service_uuids=service_uuids,
            prices=prices
        )
        return pricing_response
