import logging
import os

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection as db_connection
from django.db.utils import OperationalError
from rest_framework import permissions, response, status, views

from core.constants import ENV_BLACKLIST

logger = logging.getLogger(__name__)


class HealthCheckView(views.APIView):
    permission_classes = [permissions.AllowAny, ]

    def get(self, request):
        is_healthy = True
        # verify if blacklisted environment vars is not available
        blacklisted_envs = ENV_BLACKLIST.get(settings.LEVEL, None)
        # we loop through the blacklisted vars for the current env and
        # if there is anything, we unset the healthy flag.
        for env in blacklisted_envs:
            env_value = os.environ.get(env, None)
            if env_value:
                is_healthy = False
                break
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
