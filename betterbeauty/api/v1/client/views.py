import datetime
from typing import List

from dateutil.parser import parse

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
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
from api.v1.client.constants import ErrorMessages as client_errors, NEW_YORK_LOCATION
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
    ServicePricingRequestSerializer,
    ServicePricingSerializer,
    StylistServiceListSerializer,
    TimeSlotSerializer,
)
from api.v1.stylist.constants import MAX_APPOINTMENTS_PER_REQUEST
from api.v1.stylist.serializers import StylistSerializer
from appointment.constants import ErrorMessages as appt_constants
from appointment.models import Appointment
from appointment.preview import AppointmentPreviewRequest, build_appointment_preview_dict
from appointment.types import AppointmentStatus
from client.models import Client, PreferredStylist, StylistSearchRequest
from client.types import ClientPrivacy
from core.utils import post_or_get
from core.utils import post_or_get_or_data
from integrations.ipstack import get_lat_lng_for_ip_address
from salon.models import Stylist, StylistService


class ClientProfileView(generics.CreateAPIView, generics.RetrieveUpdateAPIView):

    serializer_class = ClientProfileSerializer
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def get_object(self):
        return self.request.user

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }


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
        client = self.request.user.client
        available_stylists = Q(
            preferredstylist__client=client,
            preferredstylist__deleted_at__isnull=True
        )
        return Stylist.objects.filter(available_stylists).distinct('id')

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
        service_queryset = StylistService.objects.filter(
            Q(
                stylist__preferredstylist__client=client,
                stylist__preferredstylist__deleted_at__isnull=True
            )
        ).distinct('id')
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
        serializer = StylistSerializer(self.get_queryset(), many=True)
        response_dict = {
            'stylists': serializer.data
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
        query = post_or_get_or_data(self.request, 'search_like', '')
        latitude = post_or_get_or_data(self.request, 'latitude', None)
        longitude = post_or_get_or_data(self.request, 'longitude', None)
        accuracy = post_or_get_or_data(self.request, 'accuracy', 50000)
        if latitude and longitude:
            location = Point((longitude, latitude))
        else:
            ip, is_routable = get_client_ip(self.request)
            location = get_lat_lng_for_ip_address(ip)
        self.save_search_request(location)
        return self._search_stylists(query, location, accuracy)

    @staticmethod
    def _search_stylists(query: str, location: Point, accuracy: int) -> List:

        queryset = Stylist.objects.annotate(
            full_name=Concat(F('user__first_name'), Value(' '), F('user__last_name')),
            reverse_full_name=Concat(F('user__last_name'), Value(' '), F('user__first_name')),
        ).distinct('id')

        nearby_stylists = SearchStylistView._get_nearby_stylists(queryset, location, accuracy)
        if len(nearby_stylists) == 0:
            # if there is no stylist in the area, return stylist from NY
            nearby_stylists = SearchStylistView._get_nearby_stylists(
                queryset, NEW_YORK_LOCATION, accuracy)

        query_filter = (
            Q(full_name__icontains=query) |
            Q(salon__name__icontains=query) |
            Q(reverse_full_name__icontains=query)
        )
        list_of_stylists = nearby_stylists.filter(query_filter)
        # we can't use order_by('distance') here since we also need to use distinct('distance') to
        # avoid "SELECT DISTINCT ON expressions must match initial ORDER BY expressions" error,
        # So we get the results and sort by distance manually.
        return sorted(list_of_stylists, key=lambda x: x.distance)

    @staticmethod
    def _get_nearby_stylists(queryset: models.QuerySet,
                             location: Point, accuracy: int) -> models.QuerySet:
        return queryset.filter(salon__location__distance_lte=(
            location, D(m=accuracy))).annotate(distance=Distance('salon__location', location)
                                               )


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
                detail={'non_field_errors': [client_errors.ERR_PRIVACY_SETTING_PRIVATE]}
            )

        stylist_preference: PreferredStylist = PreferredStylist.objects.filter(
            client=client,
            stylist__uuid=stylist_uuid,
            deleted_at__isnull=True
        ).last()

        if not stylist_preference:
            raise exceptions.NotFound(
                detail={'non_field_errors': [appt_constants.ERR_STYLIST_DOES_NOT_EXIST]}
            )

        stylist: Stylist = stylist_preference.stylist

        followers = stylist.get_preferred_clients().filter(
            privacy=ClientPrivacy.PUBLIC
        ).exclude(id=client.id)

        return Response({
            'followers': FollowerSerializer(
                followers, context={'stylist': stylist}, many=True
            ).data
        })
