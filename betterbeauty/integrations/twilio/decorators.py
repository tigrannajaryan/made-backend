import logging
import os
from functools import wraps

from django.http import HttpResponseForbidden
from twilio.request_validator import RequestValidator


logger = logging.getLogger(__name__)


def twilio_auth_required(view_func):
    """Decorator checks whether the call made by Twilio service. INH."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # TODO: remove once after testing finishes
        twilio_signature = request.META.get('HTTP_X_TWILIO_SIGNATURE')
        logger.info('TWILIO AUTH: got twilio_signature: %s' % twilio_signature)
        if not twilio_signature:
            return HttpResponseForbidden()
        auth_token = os.environ.get('TWILIO_AUTH_TOKEN', None)
        logger.info(
            'TWILIO AUTH: got twilio token: %s' % auth_token[-5:]
            if auth_token else 'None'
        )
        validator = RequestValidator(auth_token)
        url = request.build_absolute_uri()
        url = url.replace('http://', 'https://')
        logger.info('TWILIO AUTH: got url: %s' % url)
        payload = request.POST.dict()
        logger.info('TWILIO AUTH: Payload: {0}'.format(payload))
        if not validator.validate(url, payload, twilio_signature):
            logger.info('TWILIO AUTH: validation failed')
            return HttpResponseForbidden()
        logger.info('TWILIO AUTH: validation passed')
        return view_func(request, *args, **kwargs)

    return _wrapped_view
