import datetime
from typing import List, Optional

from dateutil.parser import parse

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.postgres.search import TrigramSimilarity
from django.db import models
from django.db.models import F, Q, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ipware import get_client_ip
from rest_framework import (
    exceptions,
    generics,
    permissions,
    status,
    views,
)
from rest_framework.response import Response

from api.common.permissions import ClientPermission

from api.v1.client.constants import (ErrorMessages as client_errors, NEW_YORK_LOCATION,
                                     STYLIST_SEARCH_LIMIT, TRIGRAM_SIMILARITY
                                     )
from api.v1.client.serializers import (
    AddPreferredClientsSerializer,
    AppointmentPreviewRequestSerializer,
    AppointmentPreviewResponseSerializer,
    AppointmentSerializer,
    AppointmentUpdateSerializer,
    AvailableDateSerializer,
    ClientPreferredStylistSerializer,
    ClientProfileSerializer,
    FollowerSerializer,
    HistorySerializer,
    HomeSerializer,
    SearchStylistSerializer,
    ServicePricingRequestSerializer,
    ServicePricingSerializer,
    StylistServiceListSerializer,
    TimeSlotSerializer,
)
from api.v1.stylist.constants import MAX_APPOINTMENTS_PER_REQUEST
from appointment.constants import ErrorMessages as appt_constants
from appointment.models import Appointment
from appointment.preview import AppointmentPreviewRequest, build_appointment_preview_dict
from appointment.types import AppointmentStatus
from client.models import Client, StylistSearchRequest
from client.types import ClientPrivacy
from core.utils import post_or_get
from core.utils import post_or_get_or_data
from integrations.ipstack import get_lat_lng_for_ip_address
from salon.models import Stylist, StylistService
from salon.utils import get_default_service_uuids


class ClientProfileView(generics.CreateAPIView, generics.RetrieveUpdateAPIView):

    serializer_class = ClientProfileSerializer
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def get_object(self):
        return self.request.user


class PreferredStylistListCreateView(generics.ListCreateAPIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        client_serializer_data = ClientPreferredStylistSerializer(self.request.user.client).data
        return Response(client_serializer_data)

    def post(self, request, *args, **kwargs):
        serializer = AddPreferredClientsSerializer(
            data=request.data, context={'user': self.request.user})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response_dict = serializer.data
        return Response(response_dict, status=status.HTTP_201_CREATED)

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }


class PreferredStylistDeleteView(generics.DestroyAPIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    lookup_url_kwarg = 'uuid'
    lookup_field = 'uuid'

    def get_queryset(self):
        return self.request.user.client.preferred_stylists.all()

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }


class StylistServicesView(generics.RetrieveAPIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]
    serializer_class = StylistServiceListSerializer

    def get_queryset(self):
        return Stylist.objects.all()

    def get_object(self):
        return get_object_or_404(
            self.get_queryset(),
            uuid=self.kwargs['uuid'],
        )


class StylistServicePriceView(views.APIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ServicePricingRequestSerializer(
            data=request.data, context={'client': request.user.client})
        serializer.is_valid(raise_exception=True)
        client = self.request.user.client
        service_uuids = serializer.validated_data.get('service_uuids')
        if not service_uuids:
            stylist_uuid = serializer.validated_data.get('stylist_uuid')
            stylist = Stylist.objects.get(uuid=stylist_uuid)
            service_uuids = get_default_service_uuids(stylist, client)
        service_queryset = StylistService.objects.all()
        services = []
        for service_uuid in service_uuids:
            services.append(service_queryset.get(
                uuid=service_uuid
            ))
            # client_of_stylist can as well be None here, which is OK; in such a case
            # prices will be returned without discounts
        stylist = services[0].stylist

        return Response(
            ServicePricingSerializer({
                'service_uuids': service_uuids,
                'stylist_uuid': stylist.uuid,
            }, context={'client': client,
                        'services': services, 'stylist': stylist}).data
        )


class SearchStylistView(generics.ListAPIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        matching_stylists = self.get_queryset()
        more_results_available = True if (len(matching_stylists) > STYLIST_SEARCH_LIMIT) else False
        serializer = SearchStylistSerializer(
            matching_stylists[:STYLIST_SEARCH_LIMIT], many=True
        )
        response_dict = {
            'stylists': serializer.data,
            'more_results_available': more_results_available
        }
        return Response(response_dict, status=status.HTTP_200_OK)

    def save_search_request(self, location):
        ip, is_routable = get_client_ip(self.request)
        StylistSearchRequest.objects.create(
            requested_by=self.request.user,
            user_ip_addr=ip,
            user_location=location
        )

    def get_queryset(self):
        query: str = post_or_get_or_data(self.request, 'search_like', '')
        address_query: str = post_or_get_or_data(self.request, 'search_location', '')
        latitude: Optional[float] = post_or_get_or_data(self.request, 'latitude', None)
        longitude: Optional[float] = post_or_get_or_data(self.request, 'longitude', None)
        country: Optional[str] = self.request.user.client.country
        if latitude and longitude:
            location = Point((longitude, latitude))
        else:
            ip, is_routable = get_client_ip(self.request)
            location = get_lat_lng_for_ip_address(ip)
        self.save_search_request(location)
        return self._search_stylists(query, address_query, location, country)

    @staticmethod
    def _search_stylists(query: str, address_query: str, location: Point, country: str) -> List:

        queryset = Stylist.objects.select_related('salon', 'user').filter(
            salon__country__iexact=country, salon__location__isnull=False).annotate(
            full_name=Concat(F('user__first_name'), Value(' '), F('user__last_name')),
            reverse_full_name=Concat(F('user__last_name'), Value(' '), F('user__first_name')),
        ).distinct('id')

        list_of_stylists = SearchStylistView._get_nearby_stylists(queryset, location)
        if len(list_of_stylists) == 0:
            # if there is no stylist in the area, return stylist from NY
            list_of_stylists = SearchStylistView._get_nearby_stylists(
                queryset, NEW_YORK_LOCATION)

        if query:
            list_of_stylists = list_of_stylists.annotate(
                full_name_similarity=TrigramSimilarity('full_name', query),
                salon_name_similarity=TrigramSimilarity('salon__name', query),
                reverse_full_name_similarity=TrigramSimilarity('reverse_full_name', query),
                service_name_similarity=TrigramSimilarity('services__name', query)
            ).filter(
                Q(full_name_similarity__gt=TRIGRAM_SIMILARITY) |
                Q(salon_name_similarity__gt=TRIGRAM_SIMILARITY) |
                Q(service_name_similarity__gt=TRIGRAM_SIMILARITY) |
                Q(full_name__icontains=query) |
                Q(salon__name__icontains=query) |
                Q(reverse_full_name__icontains=query) |
                Q(services__name__icontains=query)
            )

        if address_query:
            list_of_stylists = list_of_stylists.annotate(
                salon_city_similarity=TrigramSimilarity('salon__city', address_query)
            ).filter(
                Q(salon_city_similarity__gt=TRIGRAM_SIMILARITY) |
                Q(salon__state__icontains=address_query) |
                Q(salon__address__icontains=address_query) |
                Q(salon__zip_code__icontains=address_query)
            )

        # we can't use order_by('distance') here since we also need to use distinct('distance') to
        # avoid "SELECT DISTINCT ON expressions must match initial ORDER BY expressions" error,
        # So we get the results and sort by distance manually.
        return sorted(list_of_stylists, key=lambda x: x.distance)[:STYLIST_SEARCH_LIMIT + 1]

    @staticmethod
    def _get_nearby_stylists(queryset: models.QuerySet,
                             location: Point,) -> models.QuerySet:
        return queryset.annotate(distance=Distance('salon__location', location))


class AppointmentListCreateAPIView(generics.ListCreateAPIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]
    serializer_class = AppointmentSerializer

    def get_serializer_context(self):
        stylist_uuid = post_or_get_or_data(self.request, 'stylist_uuid', None)
        stylist = None
        if stylist_uuid:
            stylist = Stylist.objects.get(uuid=stylist_uuid)
        return {
            'user': self.request.user,
            'stylist': stylist
        }

    def get_queryset(self):
        client = self.request.user.client

        date_from_str = post_or_get(self.request, 'date_from')
        date_to_str = post_or_get(self.request, 'date_to')

        exclude_statuses = [
            AppointmentStatus.CANCELLED_BY_CLIENT,
            AppointmentStatus.CANCELLED_BY_STYLIST
        ]
        include_cancelled = post_or_get(self.request, 'include_cancelled', False) == 'true'
        if include_cancelled:
            exclude_statuses = None

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

        return client.get_appointments_in_datetime_range(
            datetime_from, datetime_to, exclude_statuses=exclude_statuses
        ).order_by('-datetime_start_at')[:limit]


class AppointmentRetriveUpdateView(generics.RetrieveUpdateAPIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]
    serializer_class = AppointmentUpdateSerializer

    def post(self, request, *args, **kwargs):
        """Use this merely to allow using POST as PATCH"""
        return self.partial_update(request, *args, **kwargs)

    def get_serializer_context(self):
        stylist = self.get_object().stylist
        return {
            'user': self.request.user,
            'stylist': stylist
        }

    def get_object(self):
        client = self.request.user.client
        appointments = Appointment.objects.filter(
            client=client
        )
        return get_object_or_404(
            appointments,
            uuid=self.kwargs['uuid']
        )


class AppointmentPreviewView(views.APIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def get_serializer_context(self):
        stylist_uuid = post_or_get_or_data(self.request, 'stylist_uuid', None)
        stylist = None
        if stylist_uuid:
            stylist = Stylist.objects.get(uuid=stylist_uuid)
        return {
            'user': self.request.user,
            'stylist': stylist,
        }

    def post(self, request):
        client: Client = self.request.user.client
        serializer = AppointmentPreviewRequestSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        stylist: Stylist = get_object_or_404(
            Stylist,
            uuid=serializer.validated_data.pop('stylist_uuid')
        )
        preview_request = AppointmentPreviewRequest(**serializer.validated_data)
        response_serializer = AppointmentPreviewResponseSerializer(
            build_appointment_preview_dict(
                stylist=stylist,
                client=client,
                preview_request=preview_request
            ),
            context=self.get_serializer_context()
        )
        return Response(response_serializer.data)


class AvailableTimeSlotView(views.APIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = AvailableDateSerializer(data=request.data, )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        stylist = get_object_or_404(
            Stylist.objects.filter(preferredstylist__client=request.user.client).distinct('id'),
            uuid=data['stylist_uuid'])
        date = data['date']
        available_slots = stylist.get_available_slots(date)
        serializer = TimeSlotSerializer(available_slots, many=True)
        return Response(data={'time_slots': serializer.data},)


class HomeView(generics.RetrieveAPIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]
    serializer_class = HomeSerializer

    def get(self, request, *args, **kwargs):
        client = self.request.user.client
        upcoming_appointments = self.get_upcoming_appointments(client)
        last_visited_appointment = self.get_last_visited_object(client)
        serializer = self.get_serializer({
            'upcoming': upcoming_appointments,
            'last_visited': last_visited_appointment
        })
        return Response(serializer.data)

    @staticmethod
    def get_upcoming_appointments(client):
        datetime_from = timezone.now().replace(hour=0, minute=0, second=0)
        datetime_to = None
        exclude_statuses = [
            AppointmentStatus.CANCELLED_BY_CLIENT,
            AppointmentStatus.CANCELLED_BY_STYLIST,
            AppointmentStatus.CHECKED_OUT
        ]
        return client.get_appointments_in_datetime_range(
            datetime_from, datetime_to, exclude_statuses=exclude_statuses
        )

    @staticmethod
    def get_last_visited_object(client) -> Appointment:
        return client.get_past_appointments().first()


class HistoryView(generics.ListAPIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]
    serializer_class = HistorySerializer

    def get(self, request, *args, **kwargs):
        client = self.request.user.client
        historical_appointments = list(self.get_historical_appointments(client))
        serializer = self.get_serializer({
            'appointments': historical_appointments,
        })
        return Response(serializer.data)

    @staticmethod
    def get_historical_appointments(client) -> models.QuerySet:
        return client.get_past_appointments()


class StylistFollowersView(views.APIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def get(self, request, stylist_uuid):
        client: Client = request.user.client
        if client.privacy == ClientPrivacy.PRIVATE:
            raise exceptions.ValidationError(
                code=status.HTTP_400_BAD_REQUEST,
                detail={'non_field_errors': [{'code': client_errors.ERR_PRIVACY_SETTING_PRIVATE}]}
            )

        try:
            stylist: Stylist = Stylist.objects.get(uuid=stylist_uuid)
        except Stylist.DoesNotExist:
            raise exceptions.NotFound(
                detail={'non_field_errors': [{'code': appt_constants.ERR_STYLIST_DOES_NOT_EXIST}]}
            )

        followers = stylist.get_preferred_clients().filter(
            privacy=ClientPrivacy.PUBLIC
        )

        return Response({
            'followers': FollowerSerializer(
                followers, context={'stylist': stylist}, many=True
            ).data
        })
