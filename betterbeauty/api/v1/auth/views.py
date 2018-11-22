from datetime import datetime, timedelta

from django.db import transaction
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_jwt.settings import api_settings
from rest_framework_jwt.views import JSONWebTokenAPIView

from api.v1.auth.serializers import PhoneSerializer, PhoneSMSCodeSerializer
from api.v1.auth.utils import create_client_profile_from_phone, create_stylist_profile_from_phone

from core.models import PhoneSMSCodes, User
from core.types import FBAccessToken, FBUserID, UserRole
from core.utils import post_or_get_or_data
from core.utils.auth import (
    client_jwt_response_payload_handler,
    jwt_response_payload_handler as stylist_jwt_response_payload_handler,
)
from core.utils.facebook import verify_fb_token
from integrations.slack import send_slack_new_user_signup
from salon.utils import create_stylist_profile_for_user

from .serializers import (
    CustomJSONWebTokenSerializer,
    CustomRefreshJSONWebTokenSerializer,
    FacebookAuthTokenSerializer,
    UserRegistrationSerializer,
)


class CustomRefreshJSONWebToken(JSONWebTokenAPIView):
    serializer_class = CustomRefreshJSONWebTokenSerializer

    def post(self, request, *args, **kwargs):

        # role denotes which app the use user is making the request from.
        # Response API structure will change based on the role
        role: str = post_or_get_or_data(request, 'role', None)
        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)
        user = serializer.object.get('user') or request.user
        token = serializer.object.get('token')
        # Consider as client if either the 'role' in the request is "client"
        # If role is not sent, check if user's role has "client" and not "stylist"
        # This will avoid users with client/stylist dual role but goes with client role or
        # client/staff dual role.
        if (role == UserRole.CLIENT) or (not role and (
                UserRole.CLIENT in user.role) and UserRole.STYLIST not in user.role):
            jwt_response_payload_handler = client_jwt_response_payload_handler
        elif (role == UserRole.STYLIST) or (not role and (
                UserRole.STYLIST in user.role)):
            # Consider as stylist if either the 'role' in the request is "stylist"
            # If role is not sent, check if User.role contains "stylist"
            jwt_response_payload_handler = stylist_jwt_response_payload_handler
        response_data = jwt_response_payload_handler(token, user, request)
        response = Response(response_data)
        if api_settings.JWT_AUTH_COOKIE:
            expiration = (datetime.utcnow() +
                          api_settings.JWT_EXPIRATION_DELTA)
            response.set_cookie(api_settings.JWT_AUTH_COOKIE,
                                token,
                                expires=expiration,
                                httponly=True)
        return response


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
                token=token, user=user, request=self.request
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


class SendCodeView(APIView):

    def post(self, request):
        serializer = PhoneSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        phone_code: PhoneSMSCodes = PhoneSMSCodes.create_or_update_phone_sms_code(
            data['phone'], role=data.get('role', UserRole.CLIENT)
        )
        phone_code.send()
        return Response(
            {}
        )


class VerifyCodeView(APIView):

    @transaction.atomic
    def post(self, request):
        serializer = PhoneSMSCodeSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        role = data.get('role', UserRole.CLIENT)

        try:
            user: User = User.objects.get(phone=data['phone'])
            if role == UserRole.CLIENT and not user.is_client():
                # Existing stylist, create client profile
                user = create_client_profile_from_phone(data['phone'], user)
            elif role == UserRole.STYLIST and not user.is_stylist():
                create_stylist_profile_for_user(user)
        except User.DoesNotExist:
            # New user. Create login
            if role == UserRole.STYLIST:
                user = create_stylist_profile_from_phone(data['phone'])
            else:
                user = create_client_profile_from_phone(data['phone'])
            send_slack_new_user_signup(user)

        api_settings.user_settings['JWT_EXPIRATION_DELTA'] = timedelta(days=365)
        jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
        jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER

        payload = jwt_payload_handler(user)
        token = jwt_encode_handler(payload)
        if role == UserRole.CLIENT:
            jwt_response_payload_handler = client_jwt_response_payload_handler
            response_payload = jwt_response_payload_handler(
                token, user, self.request
            )
        elif role == UserRole.STYLIST:
            jwt_response_payload_handler = stylist_jwt_response_payload_handler
            response_payload = jwt_response_payload_handler(
                token, user, request=self.request
            )

        return Response(response_payload)
