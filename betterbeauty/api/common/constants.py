HIGH_LEVEL_API_ERROR_CODES = {
    400: 'err_api_exception',
    401: 'err_authentication_failed',
    403: 'err_unauthorized',
    404: 'err_not_found',
    405: 'err_method_not_allowed',
}

LOW_LEVEL_JWT_ERROR_CODES = {
    'Signature has expired.': 'err_signature_expired',
    'Error decoding signature.': 'err_invalid_access_token',
    'Authentication credentials were not provided.': 'err_invalid_access_token',
}


class ErrorMessages:
    INVALID_PHONE_NUMBER = 'err_invalid_phone_number'


EMAIL_VERIFICATION_FROM_ID = 'noreply@madebeauty.com'
