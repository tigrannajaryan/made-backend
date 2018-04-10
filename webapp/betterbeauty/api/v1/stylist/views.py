from rest_framework import generics

from django.shortcuts import get_object_or_404

from salon.models import Stylist
from api.common.permissions import StylistPermission
from .serializers import StylistSerializer


class StylistView(generics.RetrieveAPIView):
    serializer_class = StylistSerializer
    permission_classes = [StylistPermission, ]

    def get_object(self):
        return get_object_or_404(
            Stylist,
            user=self.request.user
        )
