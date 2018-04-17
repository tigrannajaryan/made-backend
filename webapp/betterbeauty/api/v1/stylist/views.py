from annoying.functions import get_object_or_None
from rest_framework import generics, permissions

from salon.models import Stylist
from api.common.permissions import StylistRegisterUpdatePermission
from .serializers import StylistSerializer


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
