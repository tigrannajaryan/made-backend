import datetime
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import uuid4

from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone
from oauth2client.client import (
    AccessTokenRefreshError,
    FlowExchangeError,
)

from client.models import Client
from core.constants import DEFAULT_CARD_FEE, DEFAULT_TAX_RATE
from core.models import User
from integrations.google.utils import (
    build_oauth_http_object_from_tokens,
    cancel_calendar_event,
    create_calendar_event,
    GoogleHttpErrorException,
    Http,
)
from pricing import DISCOUNT_TYPE_CHOICES
from salon.models import Stylist

from .choices import APPOINTMENT_STATUS_CHOICES
from .types import AppointmentStatus


logger = logging.getLogger(__file__)


class AppointmentManager(models.Manager):

    def get_queryset(self, *args, **kwargs):
        return super(AppointmentManager, self).get_queryset(*args, **kwargs).filter(
            deleted_at__isnull=True
        )


class AppointmentAllObjectsManager(models.Manager):
    use_in_migrations = True


class Appointment(models.Model):
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)
    stylist = models.ForeignKey(
        Stylist, related_name='appointments', related_query_name='appointment',
        on_delete=models.CASCADE
    )

    # client can be null in case if stylist adds an appointment for someone not in the system
    client = models.ForeignKey(
        Client, related_name='appointments', related_query_name='appointment',
        null=True, blank=True, on_delete=models.PROTECT
    )
    client_first_name = models.CharField(max_length=255, null=True, blank=True)
    client_last_name = models.CharField(max_length=255, null=True, blank=True)
    client_phone = models.CharField(max_length=255, null=True, blank=True)

    datetime_start_at = models.DateTimeField()

    status = models.CharField(
        max_length=30, choices=APPOINTMENT_STATUS_CHOICES, default=AppointmentStatus.NEW)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='created_appointments'
    )

    deleted_at = models.DateTimeField(null=True, default=None)
    deleted_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='deleted_appointments', null=True,
        default=None
    )

    # fields filled on checkout, all null by default
    total_client_price_before_tax = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    total_tax = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    tax_percentage = models.DecimalField(
        max_digits=5, decimal_places=3, default=float(DEFAULT_TAX_RATE) * 100,
        blank=True
    )
    card_fee_percentage = models.DecimalField(
        max_digits=5, decimal_places=3, default=float(DEFAULT_CARD_FEE) * 100,
        blank=True
    )
    total_card_fee = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    grand_total = models.DecimalField(
        max_digits=4, decimal_places=0, null=True, blank=True)
    has_tax_included = models.NullBooleanField(null=True, default=None)
    has_card_fee_included = models.NullBooleanField(null=True, default=None)

    # fields holding Google calendar references for this appointment
    client_google_calendar_id = models.CharField(
        max_length=512, null=True, blank=True, default=None)
    client_google_calendar_added_at = models.DateTimeField(
        null=True, blank=True, default=None)
    stylist_google_calendar_id = models.CharField(
        max_length=512, null=True, blank=True, default=None)
    stylist_google_calendar_added_at = models.DateTimeField(
        null=True, blank=True, default=None)

    # fields holding references to notifications sent for this appointment
    stylist_new_appointment_notification = models.ForeignKey(
        'notifications.Notification', null=True, blank=True, default=None,
        on_delete=models.SET_NULL
    )
    stylist_new_appointment_notification_sent_at = models.DateTimeField(
        null=True, blank=True, default=None
    )

    objects = AppointmentManager()
    all_objects = AppointmentAllObjectsManager()

    class Meta:
        db_table = 'appointment'

    def __str__(self):
        return '{0}: {1} - {2}'.format(
            self.datetime_start_at,
            self.get_client_full_name(),
            self.stylist.get_full_name()
        )

    def get_client_full_name(self):
        if self.client:
            return self.client.user.get_full_name()
        return '{0} {1}'.format(
            self.client_first_name, self.client_last_name
        )

    @transaction.atomic
    def set_status(self, status: AppointmentStatus, updated_by: User):
            self.status = status
            self.save(update_fields=['status', ])
            self.append_status_history(updated_by=updated_by)

    def append_status_history(self, updated_by: User):
        current_now = self.stylist.get_current_now()
        AppointmentStatusHistory.objects.create(appointment=self,
                                                status=self.status,
                                                updated_at=current_now,
                                                updated_by=updated_by)

    @property
    def duration(self) -> datetime.timedelta:
        return self.stylist.service_time_gap

    def create_stylist_google_calendar_event(self):
        """Add event to google calendar of a stylist"""
        stylist: Stylist = self.stylist
        client: Optional[Client] = self.client
        if self.stylist_google_calendar_id:  # event already created
            return
        if not (stylist.google_access_token and stylist.google_refresh_token):  # no credentials
            return
        if self.status not in [
            AppointmentStatus.NEW, AppointmentStatus.CHECKED_OUT
        ]:  # we should only allow creation for new and checked out states
            return

        # build event notes/description from the template. Potentially there will
        # be slightly different templates for client's and stylist's calendars
        if client and self.created_by == client.user:
            # appointment was created by Client
            description = render_to_string(
                'google_calendar/appointment_created_by_client_body.txt',
                context={'appointment': self})
            summary = render_to_string(
                'google_calendar/appointment_created_by_client_title.txt',
                context={'appointment': self})
        else:
            description = render_to_string(
                'google_calendar/appointment_created_by_stylist_body.txt',
                context={'appointment': self})
            summary = render_to_string(
                'google_calendar/appointment_created_by_stylist_title.txt',
                context={'appointment': self})
        try:
            # actually try to create calendar event
            http_auth: Http = build_oauth_http_object_from_tokens(
                access_token=stylist.google_access_token,
                refresh_token=stylist.google_refresh_token,
                model_object_to_update=stylist,
                access_token_field='google_access_token'
            )
            if not http_auth:
                logger.error('Could not get Google auth for stylist {0}'.format(stylist.uuid))
                return
            event_id = create_calendar_event(
                oauth_http_object=http_auth, start_at=self.datetime_start_at,
                end_at=self.datetime_start_at + stylist.service_time_gap,
                attendees=[], summary=summary, description=description,
                location=self.stylist.salon.get_full_address())
            if event_id:
                # save event to DB for future use if operation was successful
                self.stylist_google_calendar_id = event_id
                self.stylist_google_calendar_added_at = timezone.now()
                self.save(update_fields=[
                    'stylist_google_calendar_id', 'stylist_google_calendar_added_at']
                )
        except GoogleHttpErrorException:
            # an exception caused by http transfer, e.g. a timeout or no connection
            logger.exception(
                'Could not add Google Calendar event for appointment {0}'.format(
                    self.uuid))
        except (AccessTokenRefreshError, FlowExchangeError):
            # an exception due to bad token. Log error and remove stylist's token
            # to stop retrying and allow to re-add the integration
            logger.exception(
                'Unable to use stylist token when trying to cancel appointment {0}'.format(
                    self.uuid))
            self.stylist.remove_google_oauth_token()

    def create_client_google_calendar_event(self):
        """Add event to google calendar of a client"""
        stylist: Stylist = self.stylist
        client: Optional[Client] = self.client
        if not self.client:
            return
        if self.client_google_calendar_id:  # event already created
            return
        if not (client.google_access_token and client.google_refresh_token):  # no credentials
            return
        if self.status not in [
            AppointmentStatus.NEW, AppointmentStatus.CHECKED_OUT
        ]:  # we should only allow creation for new and checked out states
            return

        # build event notes/description from the template. Potentially there will
        # be slightly different templates for client's and stylist's calendars
        if client and self.created_by == client.user:
            # appointment was created by Client
            description = render_to_string(
                'google_calendar/appointment_created_by_client_body.txt',
                context={'appointment': self})
            summary = render_to_string(
                'google_calendar/appointment_created_by_client_title.txt',
                context={'appointment': self})
        else:
            description = render_to_string(
                'google_calendar/appointment_created_by_stylist_body.txt',
                context={'appointment': self})
            summary = render_to_string(
                'google_calendar/appointment_created_by_stylist_title.txt',
                context={'appointment': self})
        try:
            # actually try to create calendar event
            http_auth: Http = build_oauth_http_object_from_tokens(
                access_token=client.google_access_token,
                refresh_token=client.google_refresh_token,
                model_object_to_update=client,
                access_token_field='google_access_token'
            )
            if not http_auth:
                logger.error('Could not get Google auth for client {0}'.format(client.uuid))
                return
            event_id = create_calendar_event(
                oauth_http_object=http_auth, start_at=self.datetime_start_at,
                end_at=self.datetime_start_at + stylist.service_time_gap,
                attendees=[], summary=summary, description=description,
                location=self.stylist.salon.get_full_address())
            if event_id:
                # save event to DB for future use if operation was successful
                self.client_google_calendar_id = event_id
                self.client_google_calendar_added_at = timezone.now()
                self.save(update_fields=[
                    'client_google_calendar_id', 'client_google_calendar_added_at']
                )
        except GoogleHttpErrorException:
            # an exception caused by http transfer, e.g. a timeout or no connection
            logger.exception(
                'Could not add Google Calendar event for appointment {0}'.format(
                    self.uuid))
        except (AccessTokenRefreshError, FlowExchangeError):
            # an exception due to bad token. Log error and remove stylist's token
            # to stop retrying and allow to re-add the integration
            logger.exception(
                'Unable to use client token when trying to cancel appointment {0}'.format(
                    self.uuid))
            self.client.remove_google_oauth_token()

    def cancel_stylist_google_calendar_event(self):
        """
        Cancel google calendar event in stylist's calendar (if exists) and clean up
        event id value from DB
        :return: None
        """
        if not self.stylist_google_calendar_id:
            return
        if not (self.stylist.google_access_token and self.stylist.google_refresh_token):
            return
        if self.status not in [
            AppointmentStatus.CANCELLED_BY_CLIENT, AppointmentStatus.CANCELLED_BY_STYLIST
        ]:
            return
        try:
            stylist: Stylist = self.stylist
            http_auth: Http = build_oauth_http_object_from_tokens(
                access_token=stylist.google_access_token,
                refresh_token=stylist.google_refresh_token,
                model_object_to_update=stylist,
                access_token_field='google_access_token'
            )
            if not http_auth:
                logger.error('Could not get Google auth for stylist {0}'.format(
                    stylist.uuid
                ))
                return
            if cancel_calendar_event(
                    oauth_http_object=http_auth,
                    event_id=self.stylist_google_calendar_id
            ):
                self.stylist_google_calendar_id = None
                self.save(update_fields=['stylist_google_calendar_id', ])

        except GoogleHttpErrorException:
            # an exception caused by http transfer, e.g. a timeout or no connection
            logger.exception(
                'Could not cancel Google Calendar event for appointment {0}'.format(
                    self.uuid
                )
            )
        except (AccessTokenRefreshError, FlowExchangeError):
            # an exception due to bad token. Log error and remove stylist's token
            # to stop retrying and allow to re-add the integration
            logger.exception(
                'Unable to use stylist token when trying to cancel appointment {0}'.format(
                    self.uuid))
            self.stylist.remove_google_oauth_token()

    def cancel_client_google_calendar_event(self):
        """
        Cancel google calendar event in client's calendar (if exists) and clean up
        event id value from DB
        :return: None
        """
        if not self.client_google_calendar_id:
            return
        if not self.client:
            return
        client: Client = self.client
        if not (client.google_access_token and client.google_refresh_token):
            return
        if self.status not in [
            AppointmentStatus.CANCELLED_BY_CLIENT, AppointmentStatus.CANCELLED_BY_STYLIST
        ]:
            return
        try:
            http_auth: Http = build_oauth_http_object_from_tokens(
                access_token=client.google_access_token,
                refresh_token=client.google_refresh_token,
                model_object_to_update=client,
                access_token_field='google_access_token'
            )
            if not http_auth:
                logger.error('Could not get Google auth for client {0}'.format(
                    client.uuid
                ))
                return
            if cancel_calendar_event(
                    oauth_http_object=http_auth,
                    event_id=self.client_google_calendar_id
            ):
                self.client_google_calendar_id = None
                self.save(update_fields=['client_google_calendar_id', ])

        except GoogleHttpErrorException:
            # an exception caused by http transfer, e.g. a timeout or no connection
            logger.exception(
                'Could not cancel Google Calendar event for appointment {0}'.format(
                    self.uuid
                )
            )
        except (AccessTokenRefreshError, FlowExchangeError):
            # an exception due to bad token. Log error and remove stylist's token
            # to stop retrying and allow to re-add the integration
            logger.exception(
                'Unable to use client token when trying to cancel appointment {0}'.format(
                    self.uuid))
            self.client.remove_google_oauth_token()


class AppointmentStatusHistory(models.Model):
    appointment = models.ForeignKey(Appointment, related_name='status_history',
                                    on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=APPOINTMENT_STATUS_CHOICES,
                              default=AppointmentStatus.NEW)
    updated_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, related_name='appointment_updates',
                                   on_delete=models.PROTECT)

    class Meta:
        db_table = 'appointment_status_history'


class AppointmentService(models.Model):
    appointment = models.ForeignKey(
        Appointment, related_name='services', on_delete=models.CASCADE,
        related_query_name='service'
    )
    uuid = models.UUIDField(unique=True, default=uuid4, editable=False)

    service_uuid = models.UUIDField()
    service_name = models.CharField(max_length=255)

    regular_price = models.DecimalField(max_digits=6, decimal_places=2)
    calculated_price = models.DecimalField(max_digits=6, decimal_places=2)
    client_price = models.DecimalField(max_digits=6, decimal_places=2)

    applied_discount = models.CharField(choices=DISCOUNT_TYPE_CHOICES, null=True, max_length=30)
    is_price_edited = models.BooleanField(default=False)
    discount_percentage = models.PositiveIntegerField(default=0)

    duration = models.DurationField(blank=True, null=True)

    is_original = models.BooleanField(
        verbose_name='Service with which appointment was created'
    )

    class Meta:
        db_table = 'appointment_service'

    def set_client_price(self, client_price: Decimal, commit: bool=True):
        # before applying the client price, we need to apply original discounts to it
        appointment: Appointment = self.appointment
        original_service: Optional[AppointmentService] = appointment.services.filter(
            is_original=True, applied_discount__isnull=False
        ).exclude(id=self.id).first() if appointment else None
        if original_service:
            self.applied_discount = original_service.applied_discount
            self.discount_percentage = original_service.discount_percentage
            price_with_discount = client_price * Decimal(
                1 - original_service.discount_percentage / 100.0
            )
            client_price = Decimal(price_with_discount).quantize(1, ROUND_HALF_UP)
        self.client_price = float(client_price)
        self.is_price_edited = True
        if commit:
            self.save(update_fields=[
                'client_price', 'is_price_edited', 'applied_discount', 'discount_percentage'
            ])
