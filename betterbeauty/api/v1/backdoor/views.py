import datetime

import re
from typing import Optional

from django.utils import timezone
from rest_framework import response, status, views

from api.common.permissions import BackdoorPermission
from core.models import PhoneSMSCodes, User
from core.utils import post_or_get
from salon.models import ClientOfStylist


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
        old_client_accounts = ClientOfStylist.objects.filter(
            phone=phone,
            created_at__lt=timezone.now() - ACCOUNT_LIFETIME_THRESHOLD
        )
        if (
            not phone or
            old_client_accounts.exists() or
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
