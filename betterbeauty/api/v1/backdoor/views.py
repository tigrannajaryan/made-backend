import datetime

import re
from random import randint
from typing import Optional

from django.utils import timezone
from rest_framework import response, status, views

from api.common.permissions import BackdoorPermission
from api.v1.backdoor.constants import MAX_RETRIES_FOR_UNUSED_PHONE_NUMBER
from core.models import PhoneSMSCodes, User
from core.utils import post_or_get


RESERVED_PHONE_NUMBER_PATTERN = r'^\+1555\d{7}$'
ACCOUNT_LIFETIME_THRESHOLD = datetime.timedelta(minutes=20)


class GetAuthCodeView(views.APIView):
    permission_classes = [BackdoorPermission, ]

    def get(self, request):
        phone = post_or_get(request=request, key='phone', default=None)
        old_user_accounts = User.objects.filter(
            phone=phone,
            date_joined__lt=timezone.now() - ACCOUNT_LIFETIME_THRESHOLD
        )

        if (
            not phone or
            old_user_accounts.exists()
        ):
            return response.Response(status=status.HTTP_404_NOT_FOUND)
        match = re.search(RESERVED_PHONE_NUMBER_PATTERN, phone)
        if not match:
            return response.Response(status=status.HTTP_404_NOT_FOUND)
        sms_code: Optional[PhoneSMSCodes] = PhoneSMSCodes.objects.filter(
            phone=phone,
            redeemed_at__isnull=True
        ).order_by('generated_at').last()
        if not sms_code:
            return response.Response(status=status.HTTP_404_NOT_FOUND)

        return response.Response(
            {
                'code': sms_code.code
            }
        )


def phone_number_factory():
    return '+1555{0}'.format(randint(10**(7 - 1), (10**7) - 1))


class GetUnusedPhoneNumber(views.APIView):
    permission_classes = [BackdoorPermission, ]

    def get(self, request):
        existing_numbers = User.objects.all().values_list('phone', flat=True)

        phone_number = phone_number_factory()
        number_of_tries = 0
        while phone_number in existing_numbers and (
                number_of_tries < MAX_RETRIES_FOR_UNUSED_PHONE_NUMBER):
            phone_number = phone_number_factory()
            number_of_tries += 1

        return response.Response(
            {
                'phone': phone_number
            }
        )
