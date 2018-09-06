from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import APIException


class HttpCodeException(APIException):
    status_code = None

    def __init__(self, *args, **kwargs):
        self.status_code = kwargs['status_code']
        super(HttpCodeException, self).__init__(args, kwargs)


class ExceptionToHTTPStatusCodeMIddleware(MiddlewareMixin):

    def process_exception(self, exception):
        if isinstance(exception, HttpCodeException):
            return super(ExceptionToHTTPStatusCodeMIddleware, self).handle_exception(
                HttpCodeException())

        return super(ExceptionToHTTPStatusCodeMIddleware, self).process_exception(exception)
