from rest_framework import generics, permissions, status, views
from rest_framework.response import Response

from api.common.permissions import ClientPermission
from api.v1.client.serializers import (
    AddPreferredClientsSerializer,
    ClientPreferredStylistSerializer,
    ClientProfileSerializer,
    ServicePricingRequestSerializer,
    StylistServiceListSerializer)

from api.v1.stylist.serializers import StylistServicePricingSerializer
from client.models import ClientOfStylist
from salon.models import Stylist, StylistService


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
