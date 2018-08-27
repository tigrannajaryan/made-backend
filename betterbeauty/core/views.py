import logging

from django.core.files.storage import default_storage
from django.db import connection as db_connection
from django.db.utils import OperationalError
from rest_framework import permissions, response, status, views

logger = logging.getLogger(__name__)


class HealthCheckView(views.APIView):
    permission_classes = [permissions.AllowAny, ]

    def get(self, request):
        is_healthy = True
        # verify if RDS is available
        try:
            db_connection.ensure_connection()
        except OperationalError:
            is_healthy = False
            logging.exception('Could not get DB connection while doing health check')
        # verify if S3 is available

        try:
            assert default_storage.connection is not None
        except Exception as e:
            is_healthy = False
            logging.exception('Could not get S3 connection while doing health check')
        if is_healthy:
            return response.Response(status=status.HTTP_200_OK)
        return response.Response(status=status.HTTP_400_BAD_REQUEST)
