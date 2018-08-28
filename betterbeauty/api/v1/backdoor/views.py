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


class GetAuthCodeView(views.APIView):
    permission_classes = [BackdoorPermission, ]

    def get(self, request):
        phone = post_or_get(request=request, key='phone', default=None)
        if (
            not phone or
            User.objects.filter(phone=phone).exists() or
            ClientOfStylist.objects.filter(phone=phone).exists()
        ):
            return response.Response(status=status.HTTP_404_NOT_FOUND)
        match = re.search(RESERVED_PHONE_NUMBER_PATTERN, phone)
        if not match:
            return response.Response(status=status.HTTP_404_NOT_FOUND)
        sms_code: Optional[PhoneSMSCodes] = PhoneSMSCodes.objects.filter(
            generated_at__gt=timezone.now() - datetime.timedelta(minutes=20),
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
