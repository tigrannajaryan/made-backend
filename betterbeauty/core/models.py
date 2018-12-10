import logging
import uuid
from datetime import timedelta
from random import randint
from typing import List

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from client.constants import SMS_CODE_EXPIRY_TIME_MINUTES
from integrations.twilio import render_one_time_sms_for_phone, send_sms_message

from .choices import CLIENT_OR_STYLIST_ROLE, MOBILE_OS_CHOICES, USER_ROLE
from .constants import EnvLevel
from .types import UserRole


logger = logging.getLogger(__name__)


class BaseEmailUserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given username, email, and password.
        """
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class BaseEmailUser(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )

    objects = BaseEmailUserManager()

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        abstract = True

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name


class User(BaseEmailUser):
    role = ArrayField(models.CharField(max_length=10, choices=USER_ROLE))

    phone = models.CharField(max_length=20, unique=True, null=True, default=None)
    photo = models.ImageField(blank=True, null=True)

    facebook_id = models.CharField(max_length=255, blank=True, null=True)

    date_joined = models.DateTimeField(_('date joined'), auto_now_add=True)

    uuid = models.UUIDField(unique=True, editable=False, default=uuid.uuid4)

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS: List[str] = []

    def is_client(self) -> bool:
        return USER_ROLE.client in self.role

    def is_stylist(self) -> bool:
        return USER_ROLE.stylist in self.role

    class Meta:
        db_table = 'user'

    def __str__(self):
        full_name = self.get_full_name()
        if full_name:
            return '{0} {1}'.format(full_name, self.phone)
        elif self.phone:
            return self.phone
        return self.email


def generate_upload_file_name(instance: 'TemporaryFile', filename: str) -> str:
    uploaded_by: User = instance.uploaded_by
    path = 'user_uploads/{0}/{1}-{2}'.format(uploaded_by.uuid, instance.uuid, filename)
    return path


class TemporaryFile(models.Model):
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file = models.FileField(upload_to=generate_upload_file_name)


class PhoneSMSCodes(models.Model):
    phone = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    role = models.CharField(max_length=10, choices=USER_ROLE, default=UserRole.CLIENT.value)

    generated_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'phone_sms_codes'
        unique_together = ['phone', 'role']

    @classmethod
    def generate_code(cls) -> str:
        if settings.LEVEL in [EnvLevel.DEVELOPMENT, EnvLevel.TESTS, ]:
            code = '123456'
            logger.info('Generated SMS code: {0}'.format(code))
        else:
            code = str(randint(100000, 999999))
        return code

    def redeem_sms_code(self):
        self.redeemed_at = timezone.now()
        self.save(update_fields=['redeemed_at'])

    @classmethod
    def validate_sms_code(cls, phone: str, code: str, role: str=UserRole.CLIENT)-> bool:
        try:
            phone_sms_code = cls.objects.get(
                phone=phone, code=code, expires_at__gte=timezone.now(),
                role=role, redeemed_at=None)
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
    def create_or_update_phone_sms_code(cls, phone: str, role: str=UserRole.CLIENT):
        code = cls.generate_code()
        phone_sms_code, created = cls.objects.get_or_create(phone=phone, role=role, defaults={
            'code': code,
            'generated_at': timezone.now(),
            'expires_at': timezone.now() + timedelta(minutes=SMS_CODE_EXPIRY_TIME_MINUTES),
            'redeemed_at': None,
        })
        if not created:
            phone_sms_code = phone_sms_code.update_phone_sms_code()
        return phone_sms_code

    def send(self):
        to_phone: str = self.phone
        code = self.code
        message = render_one_time_sms_for_phone(code)
        send_sms_message(
            to_phone=to_phone,
            body=message,
            role=str(self.role)
        )


class AnalyticsSession(models.Model):
    uuid = models.UUIDField(editable=False, unique=True)
    server_timestamp = models.DateTimeField(auto_now_add=True)
    client_timestamp = models.DateTimeField()
    user_role = models.CharField(max_length=16, choices=CLIENT_OR_STYLIST_ROLE)
    app_version = models.CharField(max_length=16)
    app_build = models.IntegerField()
    extra_data = JSONField(default=dict, blank=True, null=True)
    app_os = models.CharField(max_length=16, choices=MOBILE_OS_CHOICES, null=True)

    class Meta:
        db_table = 'analytics_session'


class AnalyticsView(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    server_timestamp = models.DateTimeField(auto_now_add=True)
    client_timestamp = models.DateTimeField()
    analytics_session = models.ForeignKey(AnalyticsSession, on_delete=models.CASCADE)
    # auth_session_id holds SHA1 hash for auth JWT token, if present in request
    auth_session_id = models.CharField(max_length=40, null=True, blank=True)
    view_title = models.CharField(max_length=64)
    extra_data = JSONField(default=dict, blank=True, null=True)

    class Meta:
        db_table = 'analytics_view'
