import datetime
from typing import Optional

from timezone_field import TimeZoneField

from django.contrib.postgres.fields import DateRangeField
from django.core.validators import MaxValueValidator
from django.db import models

from core.choices import WEEKDAY
from core.models import User
from core.types import Weekday


class Salon(models.Model):
    name = models.CharField(max_length=255)
    timezone = TimeZoneField()
    photo = models.ImageField(null=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=64)
    state = models.CharField(max_length=2, blank=True)
    zip_code = models.CharField(max_length=5, blank=True)
    latitude = models.DecimalField(decimal_places=8, max_digits=10, null=True, blank=True)
    longitude = models.DecimalField(decimal_places=8, max_digits=11, null=True, blank=True)

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.get_full_address())

    def get_full_address(self):
        return u', '.join((self.address, self.city, self.state))


class Stylist(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    salon = models.ForeignKey(Salon, on_delete=models.PROTECT)
    profile_photo = models.ImageField(null=True)
    work_start_at = models.TimeField()
    work_end_at = models.TimeField()

    def __str__(self):
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


class ServiceTemplate(models.Model):
    """Base service template; StylistService object will be copied from this one"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=6, decimal_places=2)
    duration = models.DurationField()

    def __str__(self):
        return 'Service template: {0}'.format(self.name)


class StylistService(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=6, decimal_places=2)
    duration = models.DurationField()
    is_enabled = models.BooleanField(default=False)

    def __str__(self):
        return 'Service: {0} by {1}'.format(self.name, self.stylist)


class StylistServicePhotoSample(models.Model):
    stylist_service = models.ForeignKey(
        StylistService, on_delete=models.CASCADE, related_name='photo_samples')
    photo = models.ImageField()


class StylistAvailableDay(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, related_name='available_days')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)

    class Meta:
        unique_together = ('stylist', 'weekday', )


class StylistWeekdayDiscount(models.Model):
    stylist = models.ForeignKey(
        Stylist, on_delete=models.CASCADE, related_name='weekday_discounts')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])

    class Meta:
        unique_together = ('stylist', 'weekday', )


class StylistFirstTimeBookDiscount(models.Model):
    stylist = models.OneToOneField(
        Stylist, on_delete=models.CASCADE, related_name='first_time_book_discount')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])

    def __str__(self):
        return '{0}% ({1})'.format(
            self.discount_percent, self.stylist
        )


class StylistDateRangeDiscount(models.Model):
    stylist = models.ForeignKey(
        Stylist, on_delete=models.CASCADE, related_name='date_range_discounts')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])
    dates = DateRangeField()
    # TODO: enforce uniqueness on date range. Django doesn't support it directly


class StylistEarlyRebookDiscount(models.Model):
    stylist = models.OneToOneField(
        Stylist, on_delete=models.CASCADE, related_name='early_rebook_discount')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])
    minrebook_interval = models.DurationField()
