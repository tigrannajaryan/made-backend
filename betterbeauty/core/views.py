import logging
import os
import random
from typing import Union

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connection as db_connection
from django.db.utils import OperationalError
from django.http import HttpResponseRedirect
from rest_framework import permissions, response, status, views

from api.common.utils import email_verification_token
from client.models import Client
from core.constants import (
    EMAIL_VERIFICATION_FAILIURE_REDIRECT_URL,
    EMAIL_VERIFICATION_SUCCESS_REDIRECT_URL,
    ENV_BLACKLIST,
    EnvLevel,
)
from core.types import UserRole
from salon.models import Stylist

logger = logging.getLogger(__name__)


class HealthCheckView(views.APIView):
    permission_classes = [permissions.AllowAny, ]

    @staticmethod
    def _should_verify_s3_write_access():
        # We should only perform this check on production, and we'll
        # try to make it roughly once every 20 health-checks to save on
        # the S3 PUT operation costs
        if settings.LEVEL != EnvLevel.PRODUCTION:
            return False
        return random.random() < 1 / settings.AWS_S3_WRITE_ACCESS_TEST_PERIODICITY

    @staticmethod
    def _has_s3_write_access():
        """Verifies if we can actually write to s3"""
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(name=settings.AWS_STORAGE_BUCKET_NAME)
        try:
            # Instance normally should not have access to delete files,
            # so we will just try to create or overwrite existing file
            # without deleting it. It should be enough to verify the
            # PutObject / PutObjectACL operations which are essential
            bucket.put_object(
                Body=b'test', Key=settings.AWS_S3_WRITE_ACCESS_TEST_FILE_NAME,
                ACL='private')
        except (BotoCoreError, ClientError):
            logger.exception('Instance {0} failed S3 write test'.format(
                settings.AWS_INSTANCE_ID
            ))
            return False
        return True

    def get(self, request):
        is_healthy = True
        # verify if blacklisted environment vars is not available
        blacklisted_envs = ENV_BLACKLIST.get(settings.LEVEL, [])
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
            logger.exception(
                'Could not get DB connection from instance {0} while doing health check'.format(
                    settings.AWS_INSTANCE_ID
                ))
        # verify if we can write to S3 bucket
        try:
            assert default_storage.connection is not None
            if self._should_verify_s3_write_access():
                if not self._has_s3_write_access():
                    is_healthy = False
        except Exception as e:
            is_healthy = False
            logger.exception(
                'Could not get S3 connection while doing health check; instance: {0}'.format(
                    settings.AWS_INSTANCE_ID
                ))
        if is_healthy:
            return response.Response(status=status.HTTP_200_OK)
        return response.Response(status=status.HTTP_400_BAD_REQUEST)


class EmailVerificationView(views.View):

    def get(self, request):
        email = request.GET.get("email", None)
        code = request.GET.get("code", None)
        role = request.GET.get("role", None)
        uuid = request.GET.get("u", None)
        if not (email and code and role):
            raise KeyError
        client_or_stylist: Union[Client, Stylist] = None
        if role == UserRole.CLIENT.value:
            client_or_stylist = Client.objects.get(email=email, uuid=uuid)
        elif role == UserRole.STYLIST.value:
            client_or_stylist = Stylist.objects.get(email=email, uuid=uuid)
        is_valid_code = email_verification_token.check_token(client_or_stylist, code)
        if is_valid_code:
            client_or_stylist.email_verified = True
            client_or_stylist.save()
            return HttpResponseRedirect(
                redirect_to=EMAIL_VERIFICATION_SUCCESS_REDIRECT_URL)
        return HttpResponseRedirect(redirect_to=EMAIL_VERIFICATION_FAILIURE_REDIRECT_URL)
