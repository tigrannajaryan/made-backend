from rest_framework_jwt.settings import api_settings as jwt_api_settings, api_settings

from api.v1.auth.serializers import AuthTokenSerializer, ClientAuthTokenSerializer
from core.models import User


def jwt_response_payload_handler(token, user=None, orig_iat=None, request=None):
    return AuthTokenSerializer({
        'token': token,
        'expires_in': jwt_api_settings.JWT_EXPIRATION_DELTA.total_seconds(),
        'role': user.role,
    }, context={'user': user}).data


def client_jwt_response_payload_handler(token, user=None, orig_iat=None, request=None):
    return ClientAuthTokenSerializer({
        'token': token,
        'expires_in': jwt_api_settings.JWT_EXPIRATION_DELTA.total_seconds(),
        'role': user.role,
    }, context={'user': user}).data


def custom_jwt_payload_handler(user: User, role: str):
    default_handler = api_settings.JWT_PAYLOAD_HANDLER
    payload = default_handler(user)
    payload['role'] = role
    return payload
