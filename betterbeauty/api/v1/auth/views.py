from datetime import timedelta

from django.db import transaction
from rest_framework import exceptions, status, views
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.views import JSONWebTokenAPIView

from api.v1.auth.serializers import PhoneSerializer, PhoneSMSCodeSerializer
from api.v1.auth.utils import create_client_profile_from_phone
from client.models import PhoneSMSCodes

from core.models import User
from core.types import FBAccessToken, FBUserID
from core.utils.auth import client_jwt_response_payload_handler
from core.utils.facebook import verify_fb_token

from .serializers import (
    CustomJSONWebTokenSerializer,
    CustomRefreshJSONWebTokenSerializer,
    FacebookAuthTokenSerializer,
    UserRegistrationSerializer,
)


class CustomRefreshJSONWebToken(JSONWebTokenAPIView):
    serializer_class = CustomRefreshJSONWebTokenSerializer


class CustomObtainJWTToken(JSONWebTokenAPIView):
    serializer_class = CustomJSONWebTokenSerializer


class RegisterUserView(CreateAPIView):
    serializer_class = UserRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            user = serializer.save()
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            jwt_response_payload_handler = api_settings.JWT_RESPONSE_PAYLOAD_HANDLER

            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)
            return Response(jwt_response_payload_handler(
                token, user, self.request
            ))


class FBRegisterLoginView(APIView):

    def post(self, request):
        serializer = FacebookAuthTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        fb_user_id: FBUserID = serializer.validated_data['fb_user_id']
        fb_access_token: FBAccessToken = serializer.validated_data['fb_access_token']

        is_valid = verify_fb_token(
            fb_access_token, fb_user_id
        )
        if not is_valid:
            return Response(
                {'error': 'Facebook token invalid'}, status=status.HTTP_401_UNAUTHORIZED
            )

        user = User.objects.filter(facebook_id=fb_user_id).last()
        if not user:
            user = serializer.save()

        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        jwt_response_payload_handler = api_settings.JWT_RESPONSE_PAYLOAD_HANDLER

        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)

        return Response(jwt_response_payload_handler(
            token, user, self.request
        ))


class SendCodeView(views.APIView):

    def post(self, request):
        serializer = PhoneSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.data
        PhoneSMSCodes.create_or_update_phone_sms_code(data['phone'])
        return Response(
            {}
        )


class VerifyCodeView(views.APIView):

    @transaction.atomic
    def post(self, request):
        serializer = PhoneSMSCodeSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        is_valid_code: bool = PhoneSMSCodes.validate_sms_code(
            phone=data['phone'], code=data['code'])
        if is_valid_code:
            try:
                user: User = User.objects.get(phone=data['phone'])
                if not user.is_client():
                    # Existing stylist, create client profile
                    user = create_client_profile_from_phone(data['phone'], user)
            except User.DoesNotExist:
                # New user. Create login
                user = create_client_profile_from_phone(data['phone'])

            api_settings.user_settings['JWT_EXPIRATION_DELTA'] = timedelta(days=365)
            jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
            jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

            jwt_response_payload_handler = client_jwt_response_payload_handler

            payload = jwt_payload_handler(user)
            token = jwt_encode_handler(payload)
            return Response(jwt_response_payload_handler(
                token, user, payload['orig_iat'], self.request
            ))
        else:
            raise exceptions.AuthenticationFailed()
