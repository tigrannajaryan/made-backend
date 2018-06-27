from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_jwt.settings import api_settings

from core.models import User
from core.types import FBAccessToken, FBUserID
from core.utils.facebook import verify_fb_token

from .serializers import FacebookAuthTokenSerializer, UserRegistrationSerializer


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
