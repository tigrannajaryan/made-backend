import datetime
import logging
import uuid

from typing import List, Optional, Tuple

from django.conf import settings
from django.contrib.gis.db.models.fields import PointField
from django.contrib.postgres.fields import DateRangeField
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from timezone_field import TimeZoneField

from appointment.types import AppointmentStatus
from appointment.utils import get_appointments_in_datetime_range
from client.models import Client, ClientOfStylist, PreferredStylist
from core.choices import WEEKDAY
from core.models import User
from core.types import Weekday
from integrations.gmaps import GeocodeValidAddress
from .choices import INVITATION_STATUS_CHOICES
from .contstants import DEFAULT_SERVICE_GAP_TIME_MINUTES
from .types import InvitationStatus, TimeSlot, TimeSlotAvailability

logger = logging.getLogger(__name__)


class StylistServiceManager(models.Manager):
    def get_queryset(self, *args, **kwargs):
        return super(StylistServiceManager, self).get_queryset(*args, **kwargs).filter(
            deleted_at__isnull=True
        )


class StylistServiceWithDeletedManager(models.Manager):
    use_in_migrations = True


class Salon(models.Model):
    name = models.CharField(max_length=255, null=True)
    timezone = TimeZoneField(default=settings.TIME_ZONE)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=64, null=True, blank=True)
    state = models.CharField(max_length=25, null=True, blank=True)
    zip_code = models.CharField(max_length=16, null=True, blank=True)
    location = PointField(geography=True, null=True)
    is_address_geocoded = models.BooleanField(default=False)
    last_geo_coded = models.DateTimeField(blank=True, null=True, default=None)

    class Meta:
        db_table = 'salon'

    def __str__(self) -> str:
        if self.name is not None:
            return '{0} ({1})'.format(self.name, self.get_full_address())
        return '[No name] ({0})'.format(self.get_full_address())

    def get_full_address(self) -> str:
        # TODO: change this to proper address generation
        return self.address

    def geo_code_address(self):
        geo_coded_address = GeocodeValidAddress(self.address).geo_code()
        if geo_coded_address:
            self.city = geo_coded_address.city
            self.state = geo_coded_address.state
            self.zip_code = geo_coded_address.zip_code
            self.location = geo_coded_address.location
            self.is_address_geocoded = True
            logger.info('Geo-coding Success', exc_info=True)
        else:
            logger.info("Geo-coding returned None")
        self.last_geo_coded = timezone.now()
        self.save(update_fields=[
            'city', 'state', 'zip_code', 'location', 'is_address_geocoded', 'last_geo_coded'])


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

    def get_available_time(self) -> Optional[datetime.timedelta]:
        if not self.is_available:
            return datetime.timedelta(0)
        return len(self.get_all_slots()) * self.stylist.service_time_gap

    def get_all_slots(self, current_time: Optional[datetime.time] = None) -> List[
            TimeSlot]:
        available_slots: List[TimeSlot] = []
        if not self.is_available:
            return available_slots
        start_at = self.work_start_at
        while start_at < self.work_end_at:
            slot_end_time = (datetime.datetime.combine(
                datetime.date.today(), start_at) + self.stylist.service_time_gap).time()
            if not current_time or (current_time and start_at > current_time):
                available_slots.append((start_at, slot_end_time))
            start_at = slot_end_time
        return available_slots


class StylistWeekdayDiscount(models.Model):
    stylist = models.ForeignKey(
        'Stylist', on_delete=models.CASCADE, related_name='weekday_discounts')
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY)
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])

    class Meta:
        db_table = 'stylist_weekday_discount'
        unique_together = ('stylist', 'weekday', )


class Stylist(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    salon = models.ForeignKey(Salon, on_delete=models.PROTECT, null=True)

    rebook_within_1_week_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    rebook_within_2_weeks_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    rebook_within_3_weeks_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    rebook_within_4_weeks_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    rebook_within_5_weeks_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    rebook_within_6_weeks_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )
    first_time_book_discount_percent = models.PositiveIntegerField(
        default=0, validators=[MaxValueValidator(100)]
    )

    is_discount_configured = models.BooleanField(default=False)
    has_invited_clients = models.BooleanField(default=False)

    service_time_gap = models.DurationField(
        default=datetime.timedelta(minutes=DEFAULT_SERVICE_GAP_TIME_MINUTES)
    )

    maximum_discount = models.IntegerField(default=None, blank=True, null=True)
    is_maximum_discount_enabled = models.BooleanField(default=False)

    instagram_url = models.CharField(max_length=2084, blank=True, null=True)
    website_url = models.CharField(max_length=2084, blank=True, null=True)

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

    def get_preferred_clients(self) -> models.QuerySet:
        preferences = PreferredStylist.objects.filter(
            stylist=self, deleted_at__isnull=True
        ).values_list('client_id', flat=True)
        return Client.objects.filter(id__in=preferences)

    def get_available_slots(self, date: datetime.date) -> List[TimeSlotAvailability]:
        datetime_from = self.with_salon_tz(datetime.datetime(date.year, date.month, date.day))
        datetime_to = self.with_salon_tz(datetime.datetime(
            date.year, date.month, date.day) + datetime.timedelta(days=1))
        available_slots: List[TimeSlotAvailability] = []
        try:
            shift = self.available_days.get(
                weekday=date.isoweekday(), is_available=True)
        except StylistAvailableWeekDay.DoesNotExist:
            return available_slots
        if date < self.get_current_now().date():
            return available_slots
        if date == self.get_current_now().date():
            slots = shift.get_all_slots(current_time=self.get_current_now().time())
        else:
            slots = shift.get_all_slots()
        for slot in slots:
            available_slots.append(
                TimeSlotAvailability(
                    start=self.with_salon_tz(datetime.datetime.combine(date, slot[0])),
                    end=self.with_salon_tz(datetime.datetime.combine(date, slot[1])),
                    is_booked=False))
        appointments = self.get_appointments_in_datetime_range(
            datetime_from, datetime_to, exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_CLIENT,
                AppointmentStatus.CANCELLED_BY_STYLIST])
        for appointment in appointments:
            appointment_start_time = appointment.datetime_start_at
            for slot in available_slots:
                if (slot.start - (self.service_time_gap / 2) <= appointment_start_time <= (
                        slot.start + (self.service_time_gap / 2))):
                    slot.is_booked = True
                    break
        return available_slots

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

    def get_or_create_weekday_discount(
            self, weekday: Weekday
    ) -> StylistWeekdayDiscount:
        return self.weekday_discounts.get_or_create(
            weekday=weekday, defaults={
                'discount_percent': 0
            }
        )[0]

    def get_current_now(self) -> datetime.datetime:
        """Return timezone-aware current datetime in the salon's timezone"""
        return self.salon.timezone.localize(
            datetime.datetime.now()
        )

    def with_salon_tz(self, date_time: datetime.datetime) -> datetime.datetime:
        """Convert supplied timezone-aware datetime to salon's timezone"""
        return date_time.astimezone(self.salon.timezone)

    def get_current_week_bounds(
            self
    ) -> Tuple[datetime.datetime, datetime.datetime]:
        """Return tuple of current week bounds"""
        current_now = self.get_current_now()
        week_start: datetime.datetime = (
            current_now - datetime.timedelta(
                days=current_now.isoweekday() - 1
            )
        ).replace(hour=0, minute=0, second=0)
        week_end: datetime.datetime = (
            current_now + datetime.timedelta(
                days=7 - current_now.isoweekday() + 1
            )
        ).replace(hour=0, minute=0, second=0)
        return week_start, week_end

    def get_appointments_in_datetime_range(
            self,
            datetime_from: Optional[datetime.datetime]=None,
            datetime_to: Optional[datetime.datetime]=None,
            including_to: Optional[bool]=False,
            exclude_statuses: Optional[List[AppointmentStatus]]=None,
            q_filter: Optional[models.Q]=None,
            **kwargs
    ) -> models.QuerySet:
        """
        Return appointments present in given datetime range.
        :param datetime_from: datetime at which first appointment is present
        :param datetime_to: datetime by which last appointment starts
        :param including_to: whether or not end datetime should be inclusive
        :param exclude_statuses: list of statuses to be excluded from the resulting query
        :param q_filter: optional list of filters to apply
        :param kwargs: any optional filter kwargs to be applied
        :return: Resulting Appointment queryset
        """

        if datetime_to and not including_to:
            datetime_to = datetime_to - self.service_time_gap

        appointments = get_appointments_in_datetime_range(
            queryset=self.appointments,
            datetime_from=datetime_from,
            datetime_to=datetime_to,
            exclude_statuses=exclude_statuses,
            **kwargs
        )

        if q_filter:
            appointments = appointments.filter(q_filter)

        return appointments.order_by('datetime_start_at')

    def get_today_appointments(
            self, upcoming_only=True,
            exclude_statuses=Optional[List[AppointmentStatus]]
    ) -> models.QuerySet:
        """Return today's appointments, aware of stylist's timezone"""
        current_now: datetime.datetime = self.get_current_now()

        datetime_from = current_now.replace(hour=0, minute=0, second=0)
        if upcoming_only is True:
            datetime_from = current_now

        next_midnight = (
            current_now + datetime.timedelta(days=1)
        ).replace(hour=0, minute=0, second=0)
        return self.get_appointments_in_datetime_range(
            datetime_from, next_midnight,
            including_to=True,
            exclude_statuses=exclude_statuses
        )

    def get_current_week_appointments(
            self, exclude_statuses=None
    ) -> models.QuerySet:
        """Return appointments in timezone-aware bounds of stylist's current week"""
        week_start, week_end = self.get_current_week_bounds()
        return self.get_appointments_in_datetime_range(
            datetime_from=week_start,
            datetime_to=week_end,
            exclude_statuses=exclude_statuses
        )

    def is_working_time(
            self, date_time: datetime.datetime
    ) -> bool:
        # FIXME: There should be extra logic to check if start and end time fall to
        # FIXME: different dates. But I guess it should be an extremely rare case for now.
        date_time = self.with_salon_tz(date_time)
        end_time = (date_time + self.service_time_gap).time()
        return self.available_days.filter(
            weekday=date_time.isoweekday(),
            work_start_at__lte=date_time.time(),
            work_end_at__gte=end_time
        ).exists()

    def is_working_day(self, date_time: datetime.datetime):
        return self.available_days.filter(
            weekday=date_time.isoweekday(), is_available=True).exists()

    def get_upcoming_visits(self):

        current_now: datetime.datetime = self.get_current_now()
        next_midnight = (
            current_now + datetime.timedelta(days=1)
        ).replace(hour=0, minute=0, second=0)

        return self.get_appointments_in_datetime_range(
            datetime_from=next_midnight,
            datetime_to=None,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_STYLIST,
                AppointmentStatus.CANCELLED_BY_CLIENT,
            ]
        )

    def get_past_visits(self):

        current_now: datetime.datetime = self.get_current_now()
        last_midnight = (current_now).replace(hour=0, minute=0, second=0)
        next_midnight = (
            current_now + datetime.timedelta(days=1)
        ).replace(hour=0, minute=0, second=0)

        return self.get_appointments_in_datetime_range(
            datetime_from=None,
            exclude_statuses=[
                AppointmentStatus.CANCELLED_BY_STYLIST,
                AppointmentStatus.CANCELLED_BY_CLIENT,
            ],
            q_filter=(Q(datetime_start_at__lt=last_midnight) | Q(
                datetime_start_at__gte=last_midnight,
                datetime_start_at__lt=next_midnight,
                status=AppointmentStatus.CHECKED_OUT)),
        )


class ServiceCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    category_code = models.CharField(max_length=25, blank=True, null=True)

    class Meta:
        db_table = 'service_category'

    def __str__(self):
        return self.name


class ServiceTemplateSet(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=255, unique=True)
    image = models.ImageField(upload_to='template_set_images', null=True, blank=True)

    sort_weight = models.IntegerField(
        default=0, verbose_name='Weight in API output; smallest go first'
    )

    description = models.TextField(blank=True)

    class Meta:
        db_table = 'service_template_set'
        ordering = ['sort_weight', 'id', ]

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
    regular_price = models.DecimalField(max_digits=6, decimal_places=2)
    duration = models.DurationField(blank=True, null=True)
    is_addon = models.BooleanField(default=False)

    class Meta:
        db_table = 'service_template'
        # unique_together = ('name', 'templateset',)

    def __str__(self):
        return 'Service template: {0}'.format(self.name)


class StylistService(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(ServiceCategory, on_delete=models.PROTECT, null=True)

    service_origin_uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    regular_price = models.DecimalField(max_digits=6, decimal_places=2)
    duration = models.DurationField(blank=True, null=True)
    is_enabled = models.BooleanField(default=False)
    is_addon = models.BooleanField(default=False)

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


class StylistDateRangeDiscount(models.Model):
    stylist = models.ForeignKey(
        Stylist, on_delete=models.CASCADE, related_name='date_range_discounts')
    discount_percent = models.PositiveIntegerField(validators=[MaxValueValidator(100)])
    dates = DateRangeField()
    # TODO: enforce uniqueness on date range. Django doesn't support it directly

    class Meta:
        db_table = 'stylist_date_range_discount'


class Invitation(models.Model):
    stylist = models.ForeignKey(Stylist, on_delete=models.CASCADE, related_name='invites')
    phone = models.CharField(max_length=15)
    status = models.CharField(
        max_length=15, choices=INVITATION_STATUS_CHOICES, default=InvitationStatus.INVITED
    )
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, default=None)
    accepted_at = models.DateTimeField(null=True, default=None)

    created_client = models.ForeignKey(
        ClientOfStylist, null=True, default=None, on_delete=models.CASCADE
    )

    class Meta:
        db_table = 'invitation'
