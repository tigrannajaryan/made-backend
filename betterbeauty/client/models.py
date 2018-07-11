from datetime import timedelta
from random import randint
from uuid import uuid4

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from utils.models import SmartModel

from client.constants import SMS_CODE_EXPIRY_TIME_MINUTES
from core.models import User


class Client(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    class Meta:
        db_table = 'client'


class ClientOfStylist(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    stylist = models.ForeignKey(
        'salon.Stylist', related_name='clients_of_stylist', on_delete=models.PROTECT)
    first_name = models.CharField(_('first name'), max_length=30, blank=True, null=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True, default=None)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, blank=True, null=True)

    class Meta:
        db_table = 'client_of_stylist'
        unique_together = (("stylist", "phone"),
                           ("stylist", "first_name", "last_name"),
                           ("stylist", "client"),)

    def get_full_name(self):
        full_name = '{0} {1}'.format(self.first_name, self.last_name)
        return full_name.strip()

    def __str__(self):
        return self.get_full_name()


class PreferredStylist(SmartModel):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='preferred_stylists')
    stylist = models.ForeignKey('salon.Stylist', on_delete=models.PROTECT)

    class Meta:
        db_table = 'preferred_stylist'
        unique_together = (("stylist", "client"),)


class PhoneSMSCodes(models.Model):
    phone = models.CharField(max_length=15, unique=True)
    code = models.CharField(max_length=6)

    generated_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'phone_sms_codes'

    @classmethod
    def generate_code(self):
        code = '123456'
        if not settings.DEBUG:
            code = str(randint(100000, 999999))
        return code

    def redeem_sms_code(self):
        self.redeemed_at = timezone.now()
        self.save(update_fields=['redeemed_at'])

    @classmethod
    def validate_sms_code(cls, phone: str, code: str)-> bool:
        try:
            phone_sms_code = cls.objects.get(
                phone=phone, code=code, expires_at__gte=timezone.now(), redeemed_at=None)
            phone_sms_code.redeem_sms_code()
            return True
        except PhoneSMSCodes.DoesNotExist:
            return False

    def update_phone_sms_code(self):
        self.code = self.generate_code()
        self.generated_at = timezone.now()
        self.expires_at = timezone.now() + timedelta(minutes=SMS_CODE_EXPIRY_TIME_MINUTES)
        self.redeemed_at = None
        self.save(update_fields=['code', 'generated_at', 'expires_at', 'redeemed_at'])
        return self

    @classmethod
    @transaction.atomic
    def create_or_update_phone_sms_code(cls, phone: str):
        code = cls.generate_code()
        phone_sms_code, created = cls.objects.get_or_create(phone=phone, defaults={
            'code': code,
            'generated_at': timezone.now(),
            'expires_at': timezone.now() + timedelta(minutes=SMS_CODE_EXPIRY_TIME_MINUTES),
            'redeemed_at': None,
        })
        if not created:
            phone_sms_code = phone_sms_code.update_phone_sms_code()
        return phone_sms_code


class StylistSearchRequest(models.Model):

    requested_by = models.ForeignKey(User, on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    user_ip_addr = models.GenericIPAddressField()

    class Meta:
        db_table = 'stylist_search_request'
