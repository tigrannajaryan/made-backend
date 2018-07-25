from django.db.models import F, Q, Value
from django.db.models.functions import Concat
import datetime

from dateutil.parser import parse
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response

from api.common.permissions import ClientPermission
from api.v1.client.serializers import (
    AppointmentSerializer,
    AddPreferredClientsSerializer,
    ClientPreferredStylistSerializer,
    ClientProfileSerializer,
    ServicePricingRequestSerializer,
    StylistServiceListSerializer, AppointmentUpdateSerializer)
from api.v1.stylist.serializers import StylistSerializer, StylistServicePricingSerializer
from appointment.models import Appointment
from client.models import ClientOfStylist
from core.utils import post_or_get_or_data
from salon.models import Stylist, StylistService

from api.v1.stylist.constants import MAX_APPOINTMENTS_PER_REQUEST
from core.utils import post_or_get


class ClientProfileView(generics.CreateAPIView, generics.RetrieveUpdateAPIView):

    serializer_class = ClientProfileSerializer
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

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

    def get_object(self):
        return Stylist.objects.get(uuid=self.kwargs['uuid'])


class StylistServicePriceView(views.APIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ServicePricingRequestSerializer(
            data=request.data, )
        serializer.is_valid(raise_exception=True)\

        service_uuid = serializer.validated_data.get('service_uuid')
        service = StylistService.objects.filter(uuid=service_uuid).last()
        client_of_stylist = ClientOfStylist.objects.get(
            client=request.user.client, stylist=service.stylist)

        return Response(
            StylistServicePricingSerializer(service, context={'client': client_of_stylist}).data
        )

    def get_object(self):
        return Stylist.objects.get(uuid=self.kwargs['uuid'])


class SearchStylistView(generics.ListAPIView):
    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = StylistSerializer(self.get_queryset(), many=True)
        response_dict = {
            'stylists': serializer.data
        }
        return Response(response_dict, status=status.HTTP_200_OK)

    def get_queryset(self):
        query = post_or_get_or_data(self.request, 'search_like', '')
        return self._search_stylists(query)

    @staticmethod
    def _search_stylists(query):

        if 1 <= len(query) < 3:
            return ClientOfStylist.objects.none()

        stylists = Stylist.objects.annotate(
            full_name=Concat(F('user__first_name'), Value(' '), F('user__last_name')),
            reverse_full_name=Concat(F('user__last_name'), Value(' '), F('user__first_name')),
        ).distinct('id')

        stylist_filter = (
            Q(full_name__icontains=query) |
            Q(salon__name__icontains=query) |
            Q(reverse_full_name__icontains=query)
        )

        return stylists.filter(stylist_filter)


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

        include_cancelled = post_or_get(self.request, 'include_cancelled', False) == 'true'
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
            datetime_from, datetime_to, include_cancelled
        )[:limit]

class AppointmentRetriveUpdateView(generics.RetrieveUpdateAPIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]
    serializer_class = AppointmentUpdateSerializer

    def get_serializer_context(self):
        stylist = self.get_object().stylist
        return {
            'user': self.request.user,
            'stylist': stylist
        }

    def get_object(self):
        return Appointment.objects.get(uuid=self.kwargs['uuid'])