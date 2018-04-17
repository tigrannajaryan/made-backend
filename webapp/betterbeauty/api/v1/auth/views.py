from rest_framework.generics import CreateAPIView
from rest_framework_jwt.settings import api_settings
from rest_framework.response import Response
from .serializers import UserRegistrationSerializer


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
