from rest_framework_jwt.settings import api_settings as jwt_api_settings

from api.v1.auth.serializers import AuthTokenSerializer


def jwt_response_payload_handler(token, user=None, request=None):
    return AuthTokenSerializer({
        'token': token,
        'expires_in': jwt_api_settings.JWT_EXPIRATION_DELTA.total_seconds(),
        'role': user.role,
    }, context={'user': user}).data
