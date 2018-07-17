from django.conf import settings

from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler

from .constants import (
    HIGH_LEVEL_API_ERROR_CODES,
    LOW_LEVEL_JWT_ERROR_CODES,
)


def formatted_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if not response and settings.CATCH_ALL_EXCEPTIONS:
        exc = APIException(exc)
        response = exception_handler(exc, context)

    if response is not None:
        high_level_code = HIGH_LEVEL_API_ERROR_CODES.get(
            response.status_code, HIGH_LEVEL_API_ERROR_CODES[400]
        )
        detail = response.data.pop('detail', None)
        detail_code = LOW_LEVEL_JWT_ERROR_CODES.get(detail, None) if detail else None
        response.data['code'] = high_level_code
        if 'field_errors' not in response.data:
            response.data['field_errors'] = {}
        if 'non_field_errors' not in response.data:
            response.data['non_field_errors'] = []
        if detail_code:
            response.data['non_field_errors'].append({'code': detail_code})
        return response

    return response
