import datetime

from annoying.functions import get_object_or_None
from rest_framework import generics, permissions, status, views
from rest_framework.response import Response

from django.db import transaction

from salon.models import Stylist, StylistService, ServiceTemplateSet
from api.common.permissions import (
    StylistPermission,
    StylistRegisterUpdatePermission,
)
from .serializers import (
    ServiceTemplateSetDetailsSerializer,
    ServiceTemplateSetListSerializer,
    StylistSerializer,
    StylistServiceSerializer,
    StylistServiceListSerializer,
)


class StylistView(
    generics.CreateAPIView, generics.RetrieveUpdateAPIView
):
    serializer_class = StylistSerializer

    permission_classes = [StylistRegisterUpdatePermission, permissions.IsAuthenticated]

    def get_object(self):
        return get_object_or_None(
            Stylist,
            user=self.request.user
        )

    def get_serializer_context(self):
        return {
            'user': self.request.user
        }


class ServiceTemplateSetListView(generics.ListAPIView):
    serializer_class = ServiceTemplateSetListSerializer
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get_queryset(self):
        return ServiceTemplateSet.objects.all()


class ServiceTemplateSetDetailsView(generics.RetrieveAPIView):
    serializer_class = ServiceTemplateSetDetailsSerializer
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    lookup_url_kwarg = 'template_set_pk'

    def get_queryset(self):
        return ServiceTemplateSet.objects.all()


class StylistServiceListView(views.APIView):
    serializer_class = StylistServiceListSerializer
    permission_classes = [StylistPermission, permissions.IsAuthenticated]

    def get(self, *args, **kwargs):
        return Response(
            StylistServiceListSerializer(
                {
                    'services': self.get_queryset(),
                }).data
        )

    def post(self, request):
        stylist = self.request.user.stylist
        serializer = StylistServiceSerializer(
            data=request.data, context={'stylist': stylist}, many=True
        )
        serializer.is_valid(raise_exception=True)
        new_entries = [item for item in serializer.validated_data if 'id' not in item]

        with transaction.atomic():
            serializer.save()

        response_status = status.HTTP_200_OK if not new_entries else status.HTTP_201_CREATED
        return Response(
            StylistServiceListSerializer(
                {
                    'services': self.get_queryset(),
                }).data,
            status=response_status
        )

    def get_queryset(self):
        return self.request.user.stylist.services.all()


class StylistServiceView(generics.DestroyAPIView):
    serializer_class = StylistServiceSerializer
    permission_classes = [StylistPermission, permissions.IsAuthenticated]
    lookup_url_kwarg = 'service_pk'

    def delete(self, request, *args, **kwargs):
        service: StylistService = self.get_object()
        current_now = service.stylist.salon.timezone.localize(
            datetime.datetime.now()
        )
        service.deleted_at = current_now
        service.save(update_fields=['deleted_at', ])
        return Response(
            StylistServiceListSerializer(
                {
                    'services': self.get_queryset(),
                }).data
        )

    def get_queryset(self):
        return self.request.user.stylist.services.all()
