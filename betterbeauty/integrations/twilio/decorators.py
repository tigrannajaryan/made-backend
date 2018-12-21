import os
from functools import wraps

from django.http import HttpResponseForbidden
from twilio.request_validator import RequestValidator


def twilio_auth_required(view_func):
    """Decorator checks whether the call made by Twilio service. INH."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        twilio_signature = request.META.get('HTTP_X_TWILIO_SIGNATURE')

        if not twilio_signature:
            return HttpResponseForbidden()

        validator = RequestValidator(os.environ.get('TWILIO_AUTH_TOKEN', None))
        url = request.build_absolute_uri()
        url = url.replace('http://', 'https://')
        payload = request.POST.dict()
        if not validator.validate(url, payload, twilio_signature):
            return HttpResponseForbidden()

        return view_func(request, *args, **kwargs)

    return _wrapped_view
