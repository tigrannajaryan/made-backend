from rest_framework_jwt.settings import api_settings as jwt_api_settings

from api.v1.auth.serializers import AuthTokenSerializer, ClientAuthTokenSerializer


def jwt_response_payload_handler(token, user=None, request=None, orig_iat=None):
    return AuthTokenSerializer({
        'token': token,
        'expires_in': jwt_api_settings.JWT_EXPIRATION_DELTA.total_seconds(),
        'created_at': orig_iat,
        'role': user.role,
    }, context={'user': user}).data


def client_jwt_response_payload_handler(token, user=None, orig_iat=None, request=None):
    return ClientAuthTokenSerializer({
        'token': token,
        'expires_in': jwt_api_settings.JWT_EXPIRATION_DELTA.total_seconds(),
        'created_at': orig_iat,
        'role': user.role,
    }, context={'user': user}).data
