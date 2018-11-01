from django.db import IntegrityError

from rest_framework import generics, parsers, permissions, status, views
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from api.common.constants import HIGH_LEVEL_API_ERROR_CODES
from api.common.permissions import ClientOrStylistPermission
from integrations.push.constants import ErrorMessages as push_errors
from integrations.push.types import PushRegistrationIdType
from integrations.push.utils import register_device, unregister_device

from .serializers import PushNotificationTokenSerializer, TemporaryImageSerializer


class TemporaryImageUploadView(generics.CreateAPIView):
    parser_classes = [parsers.MultiPartParser, ]
    permission_classes = [permissions.IsAuthenticated, ]
    serializer_class = TemporaryImageSerializer

    def get_serializer_context(self):
        return {'user': self.request.user}


class RegisterDeviceView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, ClientOrStylistPermission]

    def post(self, request):
        serializer = PushNotificationTokenSerializer(
            data=request.data, context={'user': self.request.user}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            device, created = register_device(
                user=self.request.user, user_role=data['user_role'],
                registration_id=data['device_registration_id'],
                registration_id_type=data['device_type'],
                is_development_build=data.get('is_development_build', False)
            )
        except IntegrityError:
            # duplicate APNS tokens are not allowed
            if data['device_type'] == PushRegistrationIdType.APNS:
                raise ValidationError(detail={'field_errors': {
                    'device_registration_id': [{'code': push_errors.ERR_DUPLICATE_PUSH_TOKEN}]
                }})
            raise
        if created:
            return Response({}, status=status.HTTP_201_CREATED)
        return Response({}, status=status.HTTP_200_OK)


class UnregisterDeviceView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, ClientOrStylistPermission, ]

    def post(self, request):
        serializer = PushNotificationTokenSerializer(
            data=request.data, context={'user': self.request.user}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if unregister_device(
            user=self.request.user, user_role=data['user_role'],
            registration_id=data['device_registration_id'],
            registration_id_type=data['device_type'],
            is_development_build=data.get('is_development_build', False)
        ):
            return Response({}, status=status.HTTP_204_NO_CONTENT)
        return Response({
            'code': HIGH_LEVEL_API_ERROR_CODES[404],
            'field_errors': {},
            'non_field_errors': [
                {'code': push_errors.ERR_DEVICE_NOT_FOUND}
            ]
        }, status=status.HTTP_404_NOT_FOUND)
