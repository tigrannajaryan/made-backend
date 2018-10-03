import datetime

from annoying.functions import get_object_or_None
from dateutil.parser import parse

from django.db import transaction

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
from client.models import Client, ClientOfStylist
from core.utils import (
    post_or_get,
)
from salon.models import ServiceTemplateSet, Stylist, StylistService
from .constants import ErrorMessages, MAX_APPOINTMENTS_PER_REQUEST
from .serializers import (
    AppointmentPreviewRequestSerializer,
    AppointmentPreviewResponseSerializer,
    AppointmentSerializer,
    AppointmentUpdateSerializer,
    ClientOfStylistDetailsSerializer,
    ClientSerializer,
    InvitationSerializer,
    MaximumDiscountSerializer,
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


class StylistAppointmentPreviewView(views.APIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def post(self, request):
        stylist: Stylist = self.request.user.stylist
        try:
            appointment: Appointment = stylist.appointments.get(
                uuid=request.data['appointment_uuid'])
        except Appointment.DoesNotExist:
            raise ValidationError({'detail': ErrorMessages.ERR_INVALID_APPOINTMENT_UUID})
        serializer = AppointmentPreviewRequestSerializer(
            data=request.data, context={'stylist': stylist,
                                        'appointment': appointment, 'force_start': True}
        )
        serializer.is_valid(raise_exception=True)
        client_uuid = serializer.validated_data.pop('client_uuid', None)
        client_of_stylist: ClientOfStylist = None
        if client_uuid:
            client_of_stylist = stylist.clients_of_stylist.get(
                uuid=client_uuid
            )
        preview_request = AppointmentPreviewRequest(**serializer.validated_data)
        response_serializer = AppointmentPreviewResponseSerializer(
            build_appointment_preview_dict(
                stylist=stylist,
                client_of_stylist=client_of_stylist,
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
        client_of_stylist = None
        if client_uuid:
            client_of_stylist: ClientOfStylist = get_object_or_None(
                stylist.clients_of_stylist,
                uuid=client_uuid
            )
        service_uuid = serializer.validated_data['service_uuid']

        service = self.get_queryset().filter(uuid=service_uuid).last()

        return Response(
            StylistServicePricingSerializer(
                service, context={'client_of_stylist': client_of_stylist}
            ).data
        )

    def get_queryset(self):
        return self.request.user.stylist.services.all()


class ClientListView(generics.ListAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = ClientSerializer

    def get_queryset(self):
        stylist: Stylist = self.request.user.stylist
        queryset = Client.objects.filter(preferred_stylists__stylist=stylist)
        return queryset

    def get_serializer_context(self):
        return {'stylist': self.request.user.stylist}


class ClientView(generics.RetrieveAPIView):
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    serializer_class = ClientOfStylistDetailsSerializer

    lookup_field = 'uuid'
    lookup_url_kwarg = 'client_uuid'

    def get_queryset(self):
        stylist: Stylist = self.request.user.stylist
        client_of_stylists = stylist.clients_of_stylist.all()
        return client_of_stylists

    def get_serializer_context(self):
        return {'stylist': self.request.user.stylist}
