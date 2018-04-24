from rest_framework import permissions, generics

from .serializers import TemporaryImageSerializer


class TemporaryImageUploadView(generics.CreateAPIView):

    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = TemporaryImageSerializer

    def get_serializer_context(self):
        return {'user': self.request.user}
