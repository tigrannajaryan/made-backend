import datetime
import uuid
from typing import Optional

import pytz

from django.conf import settings
from django.contrib.postgres.fields import DateRangeField
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import F

from timezone_field import TimeZoneField

from client.models import Client
from core.choices import WEEKDAY
from core.models import User
from core.types import Weekday

from .choices import INVITATION_STATUS_CHOICES
from .types import InvitationStatus


class StylistServiceManager(models.Manager):
    def get_queryset(self, *args, **kwargs):
        return super(StylistServiceManager, self).get_queryset(*args, **kwargs).filter(
            deleted_at__isnull=True
        )


class StylistServiceWithDeletedManager(models.Manager):
    use_in_migrations = True


class Salon(models.Model):
    name = models.CharField(max_length=255)
    timezone = TimeZoneField(default=settings.TIME_ZONE)
    address = models.CharField(max_length=255)
    # TODO: Remove null/blank on address sub-fields as soon as we have
    # TODO: proper address splitting mechanics in place.
    city = models.CharField(max_length=64, null=True, blank=True)
    state = models.CharField(max_length=2, null=True, blank=True)
    zip_code = models.CharField(max_length=5, null=True, blank=True)
    latitude = models.DecimalField(decimal_places=8, max_digits=10, null=True, blank=True)
    longitude = models.DecimalField(decimal_places=8, max_digits=11, null=True, blank=True)

    class Meta:
        db_table = 'salon'

    def __str__(self) -> str:
        return '{0} ({1})'.format(self.name, self.get_full_address())

    def get_full_address(self) -> str:
        # TODO: change this to proper address generation
        return self.address


class StylistAvailableWeekDay(models.Model):
    stylist = models.ForeignKey(
        'salon.Stylist', on_delete=models.CASCADE, related_name='available_days'
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)
    work_start_at = models.TimeField(null=True)
    work_end_at = models.TimeField(null=True)
    is_available = models.BooleanField(default=False)

    class Meta:
        db_table = 'stylist_available_day'
        unique_together = ('stylist', 'weekday', )

    def __str__(self):
        availability_str = ' not'
        availability_time = ''
        if self.is_available:
            availability_str = ''
            availability_time = ' {0} - {1}'.format(
                self.work_start_at,
                self.work_end_at
            )
        return '{0}:{1} available on {2}{3}'.format(
            self.stylist, availability_str, self.get_weekday_display(),
            availability_time
        )


class Stylist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    salon = models.ForeignKey(Salon, on_delete=models.PROTECT, null=True)

    rebook_within_1_week_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    rebook_within_2_weeks_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    first_time_book_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )

    class Meta:
        db_table = 'stylist'

    def __str__(self) -> str:
        return 'Stylist: {0}'.format(self.user)

    @property
    def phone(self) -> Optional[str]:
        return self.user.phone

    @property
    def first_name(self) -> Optional[str]:
        return self.user.first_name

    @property
    def last_name(self) -> Optional[str]:
        return self.user.last_name

    def get_short_name(self) -> str:
        return self.user.get_short_name()

    def get_full_name(self) -> str:
        return self.user.get_full_name()

    def get_profile_photo_url(self) -> Optional[str]:
        if self.user.photo:
            return self.user.photo.url
        return None

    def get_weekday_discount_percent(self, weekday: Weekday) -> int:
        weekday_discount = self.weekday_discounts.filter(
            weekday=weekday
        ).last()
        if weekday_discount:
            return weekday_discount.discount_percent
        return 0

    def get_date_range_discount_percent(self, date: datetime.date) -> int:
        range_discount = self.date_range_discounts.filter(
            dates__contains=date
        ).last()
        if range_discount:
            return range_discount.discount_percent
        return 0

    def get_or_create_weekday_availability(
            self, weekday: Weekday
    ) -> StylistAvailableWeekDay:
        return self.available_days.get_or_create(weekday=weekday)[0]

    def get_today_appointments(self, upcoming_only=True):
        # TODO: need to find better way to handle this
        if not self.salon:
            raise AssertionError('Stylist does not have a profile - hence no timezone info')
        current_now: datetime.datetime = pytz.timezone(self.salon.timezone).localize(
            datetime.datetime.now()
        )
        today_midnight = current_now.replace(hour=0, minute=0, second=0)
        next_midnight = current_now.replace(hour=23, minute=59, second=59)
        appointments = self.appointments.filter(
            datetime_start_at__gte=today_midnight - F('duration'),
            datetime_start_at__lte=next_midnight
        )
        if upcoming_only is True:
            appointments = appointments.filter(
                datetime_start_at__gte=current_now - F('duration'),
            )
        return appointments


class ServiceCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        db_table = 'service_category'

    def __str__(self):
        return self.name


class ServiceTemplateSet(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    image = models.ImageField(upload_to='template_set_images', null=True, blank=True)

    description = models.TextField(blank=True)

    class Meta:
        db_table = 'service_template_set'

    def __str__(self):
        return 'Service Template Set: {0}'.format(self.name)

    def get_image_url(self) -> Optional[str]:
        if self.image:
            return self.image.url
        return None


class ServiceTemplate(models.Model):
    """Base service template; StylistService object will be copied from this one"""
    category = models.ForeignKey(
        ServiceCategory, on_delete=models.PROTECT, related_name='templates'
    )

    templateset = models.ForeignKey(
        ServiceTemplateSet, on_delete=models.PROTECT,
        related_name='templates'
    )

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=6, decimal_places=2)
    duration = models.DurationField()

    class Meta:
        db_table = 'service_template'
        # unique_together = ('name', 'templateset',)

    def __str__(self):
        return 'Service template: {0}'.format(self.name)


class StylistService(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, null=True)
    service_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=6, decimal_places=2)
    duration = models.DurationField()
    is_enabled = models.BooleanField(default=False)

    deleted_at = models.DateTimeField(null=True, default=None)

    objects = StylistServiceManager()
    all_objects = StylistServiceWithDeletedManager()

    class Meta:
        db_table = 'stylist_service'

    def __str__(self):
        deleted_str = '[DELETED] ' if self.deleted_at else ''
        return '{2}{0} by {1}'.format(self.name, self.stylist, deleted_str)


class StylistServicePhotoSample(models.Model):
    stylist_service = models.ForeignKey(
        StylistService, on_delete=models.CASCADE, related_name='photo_samples')
    photo = models.ImageField()

    class Meta:
        db_table = 'stylist_service_photo_sample'


class StylistWeekdayDiscount(models.Model):
    stylist = models.ForeignKey(
        Stylist, on_delete=models.CASCADE, related_name='weekday_discounts')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])

    class Meta:
        db_table = 'stylist_weekday_discount'
        unique_together = ('stylist', 'weekday', )


class StylistDateRangeDiscount(models.Model):
    stylist = models.ForeignKey(
        Stylist, on_delete=models.CASCADE, related_name='date_range_discounts')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])
    dates = DateRangeField()
    # TODO: enforce uniqueness on date range. Django doesn't support it directly

    class Meta:
        db_table = 'stylist_date_range_discount'


class Invitation(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    status = models.CharField(
        max_length=15, choices=INVITATION_STATUS_CHOICES, default=InvitationStatus.UNSENT
    )
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, default=None)
    accepted_at = models.DateTimeField(null=True, default=None)

    created_client = models.ForeignKey(Client, null=True, default=None, on_delete=models.CASCADE)

    class Meta:
        db_table = 'invitation'
