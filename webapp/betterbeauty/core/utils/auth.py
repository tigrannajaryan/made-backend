from rest_framework_jwt.settings import api_settings as jwt_api_settings


def jwt_response_payload_handler(token, user=None, request=None):
    return {
        'token': token,
        'expires_in': jwt_api_settings.JWT_EXPIRATION_DELTA.total_seconds(),
    }
