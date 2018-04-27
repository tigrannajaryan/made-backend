import datetime
from typing import Optional

from timezone_field import TimeZoneField
import uuid

from django.contrib.postgres.fields import DateRangeField
from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models

from core.choices import WEEKDAY
from core.models import User
from core.types import Weekday


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


class Stylist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    salon = models.ForeignKey(Salon, on_delete=models.PROTECT, null=True)

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

    def get_first_time_discount_percent(self) -> int:
        if hasattr(self, 'first_time_book_discount'):
            return self.first_time_book_discount.discount_percent
        return 0

    def get_date_range_discount_percent(self, date: datetime.date) -> int:
        range_discount = self.date_range_discounts.filter(
            dates__contains=date
        ).last()
        if range_discount:
            return range_discount.discount_percent
        return 0


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


class StylistAvailableDay(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, related_name='available_days')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)

    class Meta:
        db_table = 'stylist_available_day'
        unique_together = ('stylist', 'weekday', )


class StylistWeekdayDiscount(models.Model):
    stylist = models.ForeignKey(
        Stylist, on_delete=models.CASCADE, related_name='weekday_discounts')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])

    class Meta:
        db_table = 'stylist_weekday_discount'
        unique_together = ('stylist', 'weekday', )


class StylistFirstTimeBookDiscount(models.Model):
    stylist = models.OneToOneField(
        Stylist, on_delete=models.CASCADE, related_name='first_time_book_discount')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])

    class Meta:
        db_table = 'stylist_first_time_book_discount'

    def __str__(self) -> str:
        return '{0}% ({1})'.format(
            self.discount_percent, self.stylist
        )


class StylistDateRangeDiscount(models.Model):
    stylist = models.ForeignKey(
        Stylist, on_delete=models.CASCADE, related_name='date_range_discounts')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])
    dates = DateRangeField()
    # TODO: enforce uniqueness on date range. Django doesn't support it directly

    class Meta:
        db_table = 'stylist_date_range_discount'


class StylistEarlyRebookDiscount(models.Model):
    stylist = models.OneToOneField(
        Stylist, on_delete=models.CASCADE, related_name='early_rebook_discount')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])
    minrebook_interval = models.DurationField()

    class Meta:
        db_table = 'stylist_early_rebook_discount'
