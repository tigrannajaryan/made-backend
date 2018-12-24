import datetime
from typing import Optional

from dateutil.parser import parse

from django.contrib.gis.geos import Point
from django.db import models
from django.db.models import Case, IntegerField, Q, Value, When
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

from api.v1.client.constants import (ErrorMessages as client_errors,
                                     STYLIST_SEARCH_LIMIT
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
from salon.models import Invitation, Stylist, StylistService
from salon.types import InvitationStatus
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
        return Stylist.objects.filter(deactivated_at=None)

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
        if latitude and longitude:
            location = Point((longitude, latitude))
        else:
            ip, is_routable = get_client_ip(self.request)
            location = get_lat_lng_for_ip_address(ip)
        self.save_search_request(location)
        country: Optional[str] = self.request.user.client.country or 'US'
        client_id: int = self.request.user.client.id
        return SearchStylistView._search_stylists(query, address_query, location,
                                                  country, client_id)

    @staticmethod
    def _search_stylists(query: str, address_query: str, location: Point, country: str,
                         client_id: int) -> models.query.RawQuerySet:
        '''
        :param location: This is a required parameter. If omitted the function will fail.
        '''
        point_str: str = 'POINT({0} {1})'.format(str(location.x), str(location.y))
        stylists = Stylist.objects.raw(
            '''
            SELECT
                -- Add/remove fields that are needed in the API response
                st.id as id,
                st.uuid as uuid,
                st.website_url,
                st.instagram_url,
                st.has_business_hours_set,
                first_name as user__first_name,
                last_name as user__last_name,
                "user".photo as user__photo,
                "user".phone as user__phone,
                "salon"."public_phone" as "salon__public_phone",
                salon.name AS salon__name,
                salon.address AS salon__address,
                salon.city AS salon__city,
                salon.state AS salon__state,
                salon.zip_code AS salon__zip_code,
                sp.text AS sp_text,
                services_count,
                followers_count,
                preference_uuid
            FROM
                stylist as st
            JOIN "user" on
                "user".id = st.user_id
            JOIN salon on
                salon.id = st.salon_id
            LEFT JOIN (
            --	select denormalized list of all services for all stylists
                SELECT
                    se.stylist_id,
                    string_agg(se."name", ',') AS text,
                    COUNT(se."id") AS services_count
                FROM
                    stylist_service as se
                WHERE
                    se.deleted_at ISNULL AND
                    se.is_enabled IS TRUE
                GROUP BY
                    se.stylist_id ) se ON
                st.id = se.stylist_id
            LEFT JOIN (
            --	select count of all preferred clients/followers
                    SELECT
                        COUNT(ps.id) AS followers_count,
                        ps.stylist_id
                    FROM
                        preferred_stylist as ps
                    LEFT JOIN client cli on ps.client_id = cli.id
                    WHERE
                        cli.privacy = 'public' AND
                        ps.deleted_at IS NULL
                    GROUP BY
                        ps.stylist_id
                    ) ps ON
                    st.id = ps.stylist_id
            LEFT JOIN (
                    SELECT
                        uuid as preference_uuid,
                        pfs.stylist_id
                    FROM
                        preferred_stylist as pfs
                    WHERE
                        pfs.client_id = {5} AND
                        pfs.deleted_at IS NULL
                    GROUP BY
                        pfs.stylist_id,
                        preference_uuid
                    ) pfs ON
                    st.id = pfs.stylist_id
            LEFT JOIN (
            --	select denormalized list of all specialty names and their keywords for all stylists
                SELECT
                    sp.stylist_id,
                    string_agg(speciality."name", ',') AS text,
                    string_agg(array_to_string(speciality.keywords, ' '), ' ') AS keywords
                FROM
                    stylist_specialities AS sp
                JOIN speciality ON
                    speciality.id = sp.speciality_id
                GROUP BY
                    sp.stylist_id ) sp ON
                st.id = sp.stylist_id
            WHERE
            st.deactivated_at ISNULL AND (
            -- Fuzzy search query term (omit if query is NULL)
                    (coalesce(TRIM('{0}'), '') = '') IS TRUE OR
                    '{0}' <%% (concat_ws(' ',
                        first_name,
                        last_name,
                        first_name,
                        salon.name,
                        sp.text,
                        sp.keywords,
                        se.text))
            ) AND (
            --  Fuzzy search address term (omit if address query is NULL)
                (coalesce(TRIM('{1}'), '') = '') IS TRUE  OR
                  '{1}' <%% address)
                AND '{2}' = salon."country"
            ORDER BY
                ST_Distance(salon.location,
                ST_GeogFromText('{3}'))
            LIMIT {4};'''.format(query, address_query, country, point_str,
                                 STYLIST_SEARCH_LIMIT + 1, client_id)
        )
        return stylists


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
            deactivated_at=None,
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
            Stylist.objects.filter(preferredstylist__client=request.user.client,
                                   deactivated_at=None).distinct('id'),
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
            stylist: Stylist = Stylist.objects.get(uuid=stylist_uuid, deactivated_at=None)
        except Stylist.DoesNotExist:
            raise exceptions.NotFound(
                detail={'non_field_errors': [{'code': appt_constants.ERR_STYLIST_DOES_NOT_EXIST}]}
            )

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
        followers = stylist.get_preferred_clients().filter(
            privacy=ClientPrivacy.PUBLIC
        ).annotate(name_and_photo_completeness=Case(
            When((Q(user__first_name='', user__photo='')), then=Value(4)),
            When((Q(user__first_name='') & ~Q(user__photo='')), then=Value(3)),
            When(Q(user__first_name__isnull=False, user__photo=''), then=Value(2)),
            When(Q(user__first_name__isnull=False) & ~Q(user__photo=''), then=Value(1)),
            output_field=IntegerField(),
        )).order_by('name_and_photo_completeness')

        return Response({
            'followers': FollowerSerializer(
                followers, context={'stylist': stylist}, many=True
            ).data
        })


class DeclineInvitationView(generics.DestroyAPIView):

    permission_classes = [ClientPermission, permissions.IsAuthenticated]

    def get_queryset(self):
        return Invitation.objects.filter(
            phone=self.request.user.phone, stylist__uuid=self.kwargs['uuid']
        )

    def delete(self, request, *args, **kwargs):
        invitations = self.get_queryset()
        invitations.update(status=InvitationStatus.DECLINED)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }
