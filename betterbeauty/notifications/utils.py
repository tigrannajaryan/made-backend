import datetime
import logging
from collections import Counter
from io import TextIOBase
from typing import List, Optional, Tuple

import pytz

from django.conf import settings
from django.contrib.gis.measure import D
from django.db import transaction
from django.db.models import Count, Exists, Func, Max, OuterRef, Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from appointment.models import Appointment
from appointment.types import AppointmentStatus
from client.models import Client, StylistSearchRequest
from core.models import User, UserRole
from core.utils.phone import to_international_format
from integrations.push.types import MobileAppIdType
from integrations.push.utils import has_push_notification_device
from integrations.twilio import send_sms_message
from salon.models import (
    Invitation,
    InvitationStatus,
    PreferredStylist,
    Stylist,
    StylistService,
    StylistWeekdayDiscount,
)
from .models import Notification
from .settings import NOTIFICATION_CHANNEL_PRIORITY
from .types import NotificationChannel, NotificationCode


logger = logging.getLogger(__name__)


def is_push_only(code: NotificationCode) -> bool:
    """Return True if notification to be delivered ONLY via push"""
    channels: List = NOTIFICATION_CHANNEL_PRIORITY.get(code, [])
    return frozenset(channels) == frozenset([NotificationChannel.PUSH])


def get_unsubscribe_url(target: str, uuid):
    return '{0}{1}'.format(settings.BASE_URL, reverse('email-unsubscribe', args=[target, uuid]))


@transaction.atomic()
def send_all_notifications(stdout: TextIOBase, dry_run: bool=True) -> Tuple[int, int]:
    """
    Send (or pretend if dry_run is True) ALL pending push notifications
    :param stdout: TextIOBase object representing stdout device
    :param dry_run: if set to False, no sending will actually occur
    :return: Tuple(num_sent, num_skipped)
    """
    sent = 0
    skipped = 0
    pending_notifications = Notification.objects.filter(
        user__is_active=True, pending_to_send=True, sent_at__isnull=True,
    ).select_for_update(skip_locked=True)
    for notification in pending_notifications.iterator():
        stdout.write('Going to send {0}'.format(notification.__str__()))
        if not dry_run:
            result = notification.send_and_mark_sent_now()
            if result:
                sent += 1
                stdout.write('..sent successfully')
            else:
                skipped += 1
                stdout.write('..failed to send')
    return sent, skipped


@transaction.atomic()
def generate_hint_to_first_book_notifications(dry_run=False) -> int:
    """
    Generate hint_to_first_book notifications.

    Find clients who have 0 appointments in the system, and more than 48 hours has
    passed since a client has saved/selected a preferred stylist (by checking
    preferred_stylist.created_at field). Other conditions that must be met:
    - Stylist is bookable
    - Stylist has a discount on at least one day
    - Notification table does not contain a record with code="hint_to_first_book"
    for the particular client.
    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.HINT_TO_FIRST_BOOK
    send_time_window_start = datetime.time(19, 0)
    send_time_window_end = datetime.time(21, 0)
    discard_after = timezone.now() + datetime.timedelta(days=30)
    cutoff_datetime = timezone.now() - datetime.timedelta(days=32)
    earliest_creation_datetime = timezone.now() - datetime.timedelta(hours=48)
    target = UserRole.CLIENT
    message = 'New discounts are available with your stylist! Check them out on the MADE app.'

    # Get all PreferredStylist records created more than 48 hrs ago, for which
    # - client has zero appointments
    # - client doesn't have previous booking hint notifications
    # - stylist has at least one available service
    # - stylist's profile is generally bookable, i.e. has phone and business hours set

    # Since we can't use select for update on query with aggregation, we'll just take
    # the list of ids, and will make another select based on these ids

    client_has_prior_notifications_subquery = Notification.objects.filter(
        user_id=OuterRef('client__user__id'), code=code
    )
    stylist_has_discounts_subquery = StylistWeekdayDiscount.objects.filter(
        stylist_id=OuterRef('stylist__id'), discount_percent__gte=0
    )

    client_has_registered_devices = Q(
        client__user__apnsdevice__active=True) | Q(
        client__user__gcmdevice__active=True)

    pref_client_stylist_records_ids = PreferredStylist.objects.filter(
        created_at__gte=cutoff_datetime,
        created_at__lte=earliest_creation_datetime
    ).annotate(
        client_has_notifications=Exists(client_has_prior_notifications_subquery),
        stylist_has_discounts=Exists(stylist_has_discounts_subquery)
    ).filter(
        client__appointment__isnull=True,
        stylist__services__is_enabled=True,
        stylist__user__phone__isnull=False,
        stylist__user__is_active=True,
        client__user__is_active=True,
        stylist__deactivated_at=None,
        client_has_notifications=False,
        stylist_has_discounts=True,
    ).values_list('client_id', flat=True)

    # if based on initial settings PUSH is the one and only channel that will be used
    # let's select only those clients who actually have push-enabled devices, and
    # include others only as soon as they add a push device.
    if is_push_only(code):
        pref_client_stylist_records_ids = pref_client_stylist_records_ids.filter(
            client_has_registered_devices
        )
    # actual queryset that we can lock for update on the time of
    # notifications creation
    eligible_client_ids = Client.objects.filter(
        id__in=pref_client_stylist_records_ids
    ).select_for_update(skip_locked=True)

    # For each of the eligible stylists create new Notification object

    notifications_to_create_list: List[Notification] = []

    for client in eligible_client_ids.iterator():
        notifications_to_create_list.append(Notification(
            user=client.user, target=target, code=code,
            message=message,
            discard_after=discard_after,
            send_time_window_start=send_time_window_start,
            send_time_window_end=send_time_window_end,
        ))

    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic()
def generate_hint_to_select_stylist_notifications(dry_run=False) -> int:
    """
    Generate hint_to_select_stylist notifications
    Find all clients where it's been more than 72 hours since registered and
    no stylist is selected and we have at least 1 stylist that is bookable.
    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.HINT_TO_SELECT_STYLIST
    send_time_window_start = datetime.time(19, 0)
    send_time_window_end = datetime.time(21, 0)
    discard_after = timezone.now() + datetime.timedelta(days=30)
    cutoff_datetime = timezone.now() - datetime.timedelta(days=32)
    client_joined_before_datetime = timezone.now() - datetime.timedelta(hours=72)
    target = UserRole.CLIENT
    message = (
        'We noticed that you registered but did not select a stylist. '
        'We have {0} stylists available for booking right now. '
        'Check them out on the MADE app!'
    )
    client_has_registered_devices = Q(
        user__apnsdevice__active=True) | Q(
        user__gcmdevice__active=True)

    bookable_stylists = Stylist.objects.filter(
        services__is_enabled=True,
        user__phone__isnull=False,
        user__is_active=True,
        deactivated_at__isnull=True
    ).distinct('id')

    client_has_preferred_stylists = PreferredStylist.objects.filter(
        client_id=OuterRef('id'), deleted_at__isnull=True
    )
    client_has_prior_notifications = Notification.objects.filter(
        user_id=OuterRef('user__id'), code=code
    )
    if not bookable_stylists.exists():
        # there are no bookable stylists, so we won't be sending anything
        return 0

    message = message.format(bookable_stylists.count())
    eligible_clients_ids = Client.objects.filter(
        created_at__lt=client_joined_before_datetime,
        created_at__gte=cutoff_datetime,
        user__is_active=True,
        # TODO: add is_active=True
    ).annotate(
        has_prior_notifications=Exists(client_has_prior_notifications),
        has_preferred_stylists=Exists(client_has_preferred_stylists)
    ).filter(
        has_prior_notifications=False,
        has_preferred_stylists=False
    ).values_list('id', flat=True)

    # if based on initial settings PUSH is the one and only channel that will be used
    # let's select only those clients who actually have push-enabled devices, and
    # include others only as soon as they add a push device.
    if is_push_only(code):
        eligible_clients_ids = eligible_clients_ids.filter(
            client_has_registered_devices
        )
    eligible_clients = Client.objects.filter(
        id__in=eligible_clients_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []
    for client in eligible_clients.iterator():
        notifications_to_create_list.append(Notification(
            user=client.user, target=target, code=code,
            message=message,
            discard_after=discard_after,
            send_time_window_start=send_time_window_start,
            send_time_window_end=send_time_window_end,
        ))
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic()
def generate_hint_to_rebook_notifications(dry_run=False) -> int:
    """
    Generate hint_to_rebook notifications
    Find all clients where it's been more than 4 weeks since last
    booking
    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.HINT_TO_REBOOK
    send_time_window_start = datetime.time(19, 0)
    send_time_window_end = datetime.time(21, 0)
    discard_after = timezone.now() + datetime.timedelta(days=30)
    earliest_last_booking_datetime = timezone.now() - datetime.timedelta(weeks=4)
    target = UserRole.CLIENT
    message = (
        'We noticed you haven\'t booked an appointment in the MADE '
        'in {0} weeks. Stylists have deals available today, take a look!'
    )
    bookable_stylists = Stylist.objects.filter(
        services__is_enabled=True,
        user__phone__isnull=False,
        user__is_active=True,
        deactivated_at__isnull=True
    ).distinct('id')
    if not bookable_stylists.exists():
        # there are no bookable stylists, so we won't be sending anything
        return 0

    client_has_registered_devices = Q(
        user__apnsdevice__active=True) | Q(
        user__gcmdevice__active=True)

    eligible_clients_ids = Client.objects.filter(
        user__is_active=True,
        appointment__status__in=[AppointmentStatus.NEW, AppointmentStatus.CHECKED_OUT]
    ).annotate(
        last_visit_datetime=Max('appointment__datetime_start_at'),
        notification_cnt=Count(
            'user__notification', filter=Q(
                user__notification__code=code
            )
        )
    ).filter(
        last_visit_datetime__lt=earliest_last_booking_datetime, notification_cnt=0
    ).values_list('id', flat=True)

    # if based on initial settings PUSH is the one and only channel that will be used
    # let's select only those clients who actually have push-enabled devices, and
    # include others only as soon as they add a push device.
    if is_push_only(code):
        eligible_clients_ids = eligible_clients_ids.filter(client_has_registered_devices)

    eligible_clients = Client.objects.filter(
        id__in=eligible_clients_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []
    for client in eligible_clients.iterator():
        last_visit = Appointment.objects.filter(
            status__in=[AppointmentStatus.CHECKED_OUT, AppointmentStatus.NEW],
            client=client, datetime_start_at__lte=timezone.now()
        ).order_by('datetime_start_at').last()
        if not last_visit or last_visit.datetime_start_at >= earliest_last_booking_datetime:
            continue
        week_count = int((timezone.now() - last_visit.datetime_start_at).days / 7)
        message = message.format(week_count)
        notifications_to_create_list.append(Notification(
            user=client.user, target=target, code=code,
            message=message,
            discard_after=discard_after,
            send_time_window_start=send_time_window_start,
            send_time_window_end=send_time_window_end,
        ))
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic()
def cancel_new_appointment_notification(
    appointment: Appointment
):
    """Delete new appointment notification if it's not sent yet"""
    notification: Notification = appointment.stylist_new_appointment_notification
    if notification and notification.pending_to_send:
        appointment.stylist_new_appointment_notification = None
        appointment.stylist_new_appointment_notification_sent_at = None
        appointment.save(
            update_fields=[
                'stylist_new_appointment_notification_sent_at',
                'stylist_new_appointment_notification_sent_at'
            ])
        notification.delete()


def get_earliest_time_to_send_notification_on_date(
        stylist: Stylist, date: datetime.date
) -> datetime.datetime:
    """Return minimum between 10am and start of work on a given date"""
    ten_am: datetime.datetime = stylist.salon.timezone.localize(
        datetime.datetime.combine(date, datetime.time(10, 0))
    )
    work_start: Optional[
        datetime.datetime] = stylist.get_workday_start_time(date)
    if work_start:
        return min(work_start, ten_am)
    return ten_am


@transaction.atomic()
def generate_stylist_cancelled_appointment_notification(
        appointment: Appointment
) -> int:
    """
    Generates a single notification when an appointment is cancelled by the stylist.
    :param appointment: Appointment to generate notification
    :return: number of notifications created
    """
    code = NotificationCode.STYLIST_CANCELLED_APPOINTMENT
    target = UserRole.CLIENT
    message = (
        'Your appointment at {date_time} '
        'was cancelled by the stylist'
    )
    stylist = appointment.stylist
    client = appointment.client
    # appointment must be created by client
    if not client or client.user != appointment.created_by:
        return 0
    # if appointment is not new - skip
    if appointment.status != AppointmentStatus.NEW:
        return 0
    # if it's push-only notification, and client has no push devices - skip
    if is_push_only(code) and not has_push_notification_device(
        client.user, UserRole.CLIENT
    ):
        return 0

    message = message.format(
        date_time=stylist.with_salon_tz(appointment.datetime_start_at).strftime(
            '%-I:%M%p, on %b %-d, %Y'
        ),
    )
    current_now: datetime.datetime = stylist.with_salon_tz(timezone.now())

    MINIMUM_TIME_BEFORE_APPOINTMENT_START = datetime.timedelta(minutes=30)

    notify_before_time = (
        appointment.datetime_start_at - MINIMUM_TIME_BEFORE_APPOINTMENT_START)

    stylist_today: datetime.date = current_now.date()

    TODAY_MIN = stylist.salon.timezone.localize(
        datetime.datetime.combine(
            stylist_today, datetime.time(10, 0, 0)
        )
    )

    TODAY_MAX = stylist.salon.timezone.localize(
        datetime.datetime.combine(
            stylist_today, datetime.time(20, 0, 0)
        )
    )

    TOMORROW_MIN = TODAY_MIN + datetime.timedelta(days=1)

    if TODAY_MIN <= current_now <= TODAY_MAX:
        # Immediately if current time in [10am..8pm] in client’s timezone
        send_time_window_start_datetime = current_now
    else:
        # else delay until next 10 AM
        if notify_before_time <= TOMORROW_MIN:
            # However if appointment_start_time-30min is earlier than next 10am
            # then deliver at appointment_start_time-30min
            send_time_window_start_datetime = notify_before_time
        else:
            send_time_window_start_datetime = TOMORROW_MIN

    if current_now.date() == appointment.datetime_start_at.date():
        send_time_window_end = datetime.time.max
    else:
        send_time_window_end = datetime.time(20, 0, 0)

    discard_after = stylist.with_salon_tz(
        appointment.datetime_start_at
    ) + datetime.timedelta(hours=1)

    Notification.objects.create(
        user=appointment.client.user, target=target, code=code,
        message=message,
        discard_after=discard_after,
        send_time_window_start=send_time_window_start_datetime,
        send_time_window_end=send_time_window_end,
        send_time_window_tz=stylist.salon.timezone,
        data={
            'appointment_datetime_start_at': appointment.datetime_start_at.isoformat(),
            'appointment_uuid': str(appointment.uuid)
        }
    )
    return 1


@transaction.atomic()
def generate_client_cancelled_appointment_notification(
        appointment: Appointment
) -> int:
    """
    Generates a single notification when an appointment is cancelled by the client.
    :param appointment: Appointment to generate notification
    :return: number of notifications created
    """
    code = NotificationCode.CLIENT_CANCELLED_APPOINTMENT
    target = UserRole.STYLIST
    message = (
        'Your appointment at {date_time} '
        'was cancelled by the client'
    )
    stylist = appointment.stylist
    client = appointment.client
    # appointment must be created by client
    if not client or client.user != appointment.created_by:
        return 0
    # if appointment is not new - skip
    if appointment.status != AppointmentStatus.NEW:
        return 0
    # if it's push-only notification, and stylist has no push devices - skip
    if is_push_only(code) and not has_push_notification_device(
        stylist.user, UserRole.STYLIST
    ):
        return 0

    message = message.format(
        date_time=stylist.with_salon_tz(appointment.datetime_start_at).strftime(
            '%-I:%M%p, on %b %-d, %Y'
        ),
    )
    current_now: datetime.datetime = stylist.with_salon_tz(timezone.now())

    MINIMUM_TIME_BEFORE_APPOINTMENT_START = datetime.timedelta(minutes=30)

    notify_before_time = (
        appointment.datetime_start_at - MINIMUM_TIME_BEFORE_APPOINTMENT_START)

    stylist_today: datetime.date = current_now.date()

    TODAY_MIN = stylist.salon.timezone.localize(
        datetime.datetime.combine(
            stylist_today, datetime.time(10, 0, 0)
        )
    )

    TODAY_MAX = stylist.salon.timezone.localize(
        datetime.datetime.combine(
            stylist_today, datetime.time(20, 0, 0)
        )
    )

    TOMORROW_MIN = TODAY_MIN + datetime.timedelta(days=1)

    if TODAY_MIN <= current_now <= TODAY_MAX:
        # Immediately if current time in [10am..8pm] in client’s timezone
        send_time_window_start_datetime = current_now
    else:
        # else delay until next 10 AM
        if notify_before_time <= TOMORROW_MIN:
            # However if appointment_start_time-30min is earlier than next 10am
            # then deliver at appointment_start_time-30min
            send_time_window_start_datetime = notify_before_time
        else:
            send_time_window_start_datetime = TOMORROW_MIN

    send_time_window_end = datetime.time.max

    discard_after = stylist.with_salon_tz(
        appointment.datetime_start_at
    ) + datetime.timedelta(hours=1)

    Notification.objects.create(
        user=appointment.stylist.user, target=target, code=code,
        message=message,
        discard_after=discard_after,
        send_time_window_start=send_time_window_start_datetime,
        send_time_window_end=send_time_window_end,
        send_time_window_tz=stylist.salon.timezone,
        data={
            'appointment_datetime_start_at': appointment.datetime_start_at.isoformat(),
            'appointment_uuid': str(appointment.uuid)
        }
    )
    return 1


@transaction.atomic()
def cancel_exsting_update_appointment_notification(
    appointment: Appointment
):
    Notification.objects.filter(
        code=NotificationCode.RESCHEDULED_APPOINTMENT,
        pending_to_send=True,
        data__appointment_uuid=str(appointment.uuid)
    ).delete()


@transaction.atomic()
def generate_appointment_reschedule_notification(
        appointment: Appointment, previous_datetime, previous_client_price, previous_services
) -> int:
    cancel_exsting_update_appointment_notification(appointment)
    code = NotificationCode.RESCHEDULED_APPOINTMENT
    target = UserRole.STYLIST
    message = (
        'Appointment previously at {previous_datetime} for ${client_price} {services} from '
        '{client_name} is rescheduled to {new_datetime}'
    )
    stylist: Stylist = appointment.stylist
    client: Client = appointment.client
    # if appointment is not new - skip
    if appointment.status != AppointmentStatus.NEW:
        return 0
    # if it's push-only notification, and client has no push devices - skip
    if is_push_only(code) and not has_push_notification_device(
            stylist.user, UserRole.STYLIST
    ):
        return 0

    client_name = client.user.get_full_name()
    client_name = '{0} '.format(client_name) if client_name else ''
    previous_datetime = stylist.with_salon_tz(previous_datetime).strftime(
        '%-I:%M%p, on %b %-d, %Y'
    )
    new_client_price = int(appointment.total_client_price_before_tax)
    new_services = ', '.join([s.service_name for s in appointment.services.all()])
    new_datetime = stylist.with_salon_tz(appointment.datetime_start_at).strftime(
        '%-I:%M%p, on %b %-d, %Y'
    )
    message = message.format(
        previous_datetime=previous_datetime,
        client_price=previous_client_price,
        previous_services=new_services,
        services=new_services,
        client_name=client_name,
        new_datetime=new_datetime,
    )

    # Calculate start of send window.
    # If current time is later than minimum of (stylist's day start - 30 min, 10am) -
    # schedule to send immediately. If it's not working day for stylist (can happen
    # in case if stylist set unavailability after appointment was created), we'll
    # default to 10am.
    # Otherwise, we'll delay sending to half-hour to the minimum of either day start
    # or appointment start time
    current_now: datetime.datetime = stylist.with_salon_tz(timezone.now())
    # We'll use graceful period delay of 15 minutes, to
    # allow cancelling it without sending if client cancels appointment
    GRACE_PERIOD = datetime.timedelta(minutes=15)
    # we're going to limit minimum time we can send the message before the day
    # starts
    MINIMUM_TIME_BEFORE_DAY_START = datetime.timedelta(minutes=30)
    CURRENT_NOW_WITH_GRACE_PERIOD: datetime.datetime = current_now + GRACE_PERIOD
    STYLIST_TODAY: datetime.date = current_now.date()
    # if we're composing the notification to be sent today - we'll discard it after
    # today's midnight
    TODAY_MIDNIGHT = stylist.salon.timezone.localize(
        datetime.datetime.combine(
            STYLIST_TODAY, datetime.time(0, 0, 0)
        )
    ) + datetime.timedelta(days=1)
    # there can be a situation (if it's too late today) that notification will
    # go to tomorrow
    TOMORROW_MIDNIGHT = TODAY_MIDNIGHT + datetime.timedelta(days=1)
    earliest_time_today = get_earliest_time_to_send_notification_on_date(
        stylist, STYLIST_TODAY
    )
    if current_now >= earliest_time_today:
        # if stylist already started work, or it's later than 10am - just add
        # 15 minute grace period to current time
        send_time_window_start_datetime = CURRENT_NOW_WITH_GRACE_PERIOD
    else:
        # if it's earlier than 10am or stylist's work day - set time window
        # 30 minutes earlier than work start or appointment start time,
        # but not earlier than (current time + 15 min)
        send_time_window_start_datetime = max(
            earliest_time_today - MINIMUM_TIME_BEFORE_DAY_START,
            CURRENT_NOW_WITH_GRACE_PERIOD
        )
    # there's a real chance that we've jumped to tomorrow, if appointment was created
    # just before the midnight. This means we've lost our send window for today, and
    # should create time window to use for tomorrow following the same rules as for
    # today, just honouring tomorrow's day settings
    if send_time_window_start_datetime.date() == current_now.date():
        send_time_window_start = send_time_window_start_datetime.time()
        send_time_window_end = datetime.time(23, 59, 59)
        discard_after = TODAY_MIDNIGHT
    else:
        # we're jumping to tomorrow. We'll set the start of time window to the earliest
        # time when we can send it tomorrow (i.e. min(start of day or 10am) - 30 minutes
        tomorrow_send_time_window_start_datetime = get_earliest_time_to_send_notification_on_date(
            stylist, send_time_window_start_datetime.date()
        ) - MINIMUM_TIME_BEFORE_DAY_START
        send_time_window_start = tomorrow_send_time_window_start_datetime.time()
        # we also need to adjust time window end, to avoid sending today. To do this,
        # we'll set time window just a minute before now, so it's not sent today
        send_time_window_end = (current_now - datetime.timedelta(minutes=1)).time()
        # If appointment is tomorrow - we'll set discard_after to appointment's time,
        # because it's no longer relevant after it started
        # Otherwise (if it's on a later date), we'll set it to tomorrow's midnight
        discard_after = stylist.with_salon_tz(
            min(TOMORROW_MIDNIGHT, appointment.datetime_start_at)
        )
    client_name = appointment.client.user.get_short_name()
    client_name = '{0} '.format(client_name) if client_name else ''
    stylist_name = stylist.get_short_name()
    unsubscribe_url = get_unsubscribe_url(target, stylist.uuid)
    msg_plain = render_to_string('email/notification/reschedule_apointment/body.txt',
                                 {'short_name': stylist_name,
                                  'unsubscribe_url': unsubscribe_url,
                                  'client_name': client_name,
                                  'previous_datetime': previous_datetime,
                                  'previous_services': previous_services,
                                  'previous_client_price': previous_client_price,
                                  'new_datetime': new_datetime,
                                  'new_services': new_services,
                                  'new_client_price': new_client_price,
                                  })
    msg_html = render_to_string('email/notification/reschedule_apointment/body.html',
                                {'short_name': stylist_name,
                                 'unsubscribe_url': unsubscribe_url,
                                 'previous_datetime': previous_datetime,
                                 'previous_services': previous_services,
                                 'previous_client_price': previous_client_price,
                                 'new_datetime': new_datetime,
                                 'new_services': new_services,
                                 'new_client_price': new_client_price,
                                 })
    mail_subject = render_to_string('email/notification/reschedule_apointment/subject.txt', {
        'short_name': stylist_name, 'client_name': client_name})
    Notification.objects.create(
        user=appointment.stylist.user, target=target, code=code,
        message=message,
        email_details={
            'from': settings.DEFAULT_FROM_EMAIL,
            'to': stylist.email,
            'subject': mail_subject,
            'text_content': msg_plain,
            'html_content': msg_html
        },
        discard_after=discard_after,
        forced_channel=NotificationChannel.EMAIL,
        send_time_window_start=send_time_window_start,
        send_time_window_end=send_time_window_end,
        send_time_window_tz=stylist.salon.timezone,
        data={
            'appointment_datetime_start_at': appointment.datetime_start_at.isoformat(),
            'appointment_uuid': str(appointment.uuid)
        }
    )
    return 1


@transaction.atomic()
def generate_new_appointment_notification(
        appointment: Appointment
) -> int:
    """
    Generates single notification for NEW appointment, when appointment is created
    by a client and at least 15 mins are passed since appointment creation
    (15 min is time we allow for the client to cancel without bothering the stylist).
    After notification is created, appointment is updated with reference to it

    :param appointment: Appointment to generate
    :return: number of notifications created
    """

    code = NotificationCode.NEW_APPOINTMENT
    target = UserRole.STYLIST
    message = (
        'You have a new appointment at {date_time} for ${client_price} '
        '{services} from {client_name}{client_phone}'
    )
    stylist: Stylist = appointment.stylist
    client: Client = appointment.client
    # appointment must be created by client
    if not client or client.user != appointment.created_by:
        return 0
    # if appointment is not new - skip
    if appointment.status != AppointmentStatus.NEW:
        return 0
    # if it's push-only notification, and client has no push devices - skip
    if is_push_only(code) and not has_push_notification_device(
        stylist.user, UserRole.STYLIST
    ):
        return 0

    client_name = appointment.client.user.get_full_name()

    message = message.format(
        date_time=stylist.with_salon_tz(appointment.datetime_start_at).strftime(
            '%-I:%M%p, on %b %-d, %Y'
        ),
        client_price=int(appointment.total_client_price_before_tax),
        services=', '.join([s.service_name for s in appointment.services.all()]),
        client_name='{0} '.format(client_name) if client_name else '',
        client_phone=to_international_format(client.user.phone, client.country)
    )
    # Calculate start of send window.
    # If current time is later than minimum of (stylist's day start - 30 min, 10am) -
    # schedule to send immediately. If it's not working day for stylist (can happen
    # in case if stylist set unavailability after appointment was created), we'll
    # default to 10am.
    # Otherwise, we'll delay sending to half-hour to the minimum of either day start
    # or appointment start time
    current_now: datetime.datetime = stylist.with_salon_tz(timezone.now())
    # We'll use graceful period delay of 15 minutes, to
    # allow cancelling it without sending if client cancels appointment
    GRACE_PERIOD = datetime.timedelta(minutes=15)
    # we're going to limit minimum time we can send the message before the day
    # starts
    MINIMUM_TIME_BEFORE_DAY_START = datetime.timedelta(minutes=30)
    CURRENT_NOW_WITH_GRACE_PERIOD: datetime.datetime = current_now + GRACE_PERIOD
    STYLIST_TODAY: datetime.date = current_now.date()
    # if we're composing the notification to be sent today - we'll discard it after
    # today's midnight
    TODAY_MIDNIGHT = stylist.salon.timezone.localize(
        datetime.datetime.combine(
            STYLIST_TODAY, datetime.time(0, 0, 0)
        )
    ) + datetime.timedelta(days=1)
    # there can be a situation (if it's too late today) that notification will
    # go to tomorrow
    TOMORROW_MIDNIGHT = TODAY_MIDNIGHT + datetime.timedelta(days=1)
    earliest_time_today = get_earliest_time_to_send_notification_on_date(
        stylist, STYLIST_TODAY
    )
    if current_now >= earliest_time_today:
        # if stylist already started work, or it's later than 10am - just add
        # 15 minute grace period to current time
        send_time_window_start_datetime = CURRENT_NOW_WITH_GRACE_PERIOD
    else:
        # if it's earlier than 10am or stylist's work day - set time window
        # 30 minutes earlier than work start or appointment start time,
        # but not earlier than (current time + 15 min)
        send_time_window_start_datetime = max(
            earliest_time_today - MINIMUM_TIME_BEFORE_DAY_START,
            CURRENT_NOW_WITH_GRACE_PERIOD
        )
    # there's a real chance that we've jumped to tomorrow, if appointment was created
    # just before the midnight. This means we've lost our send window for today, and
    # should create time window to use for tomorrow following the same rules as for
    # today, just honouring tomorrow's day settings
    if send_time_window_start_datetime.date() == current_now.date():
        send_time_window_start = send_time_window_start_datetime.time()
        send_time_window_end = datetime.time(23, 59, 59)
        discard_after = TODAY_MIDNIGHT
    else:
        # we're jumping to tomorrow. We'll set the start of time window to the earliest
        # time when we can send it tomorrow (i.e. min(start of day or 10am) - 30 minutes
        tomorrow_send_time_window_start_datetime = get_earliest_time_to_send_notification_on_date(
            stylist, send_time_window_start_datetime.date()
        ) - MINIMUM_TIME_BEFORE_DAY_START
        send_time_window_start = tomorrow_send_time_window_start_datetime.time()
        # we also need to adjust time window end, to avoid sending today. To do this,
        # we'll set time window just a minute before now, so it's not sent today
        send_time_window_end = (current_now - datetime.timedelta(minutes=1)).time()
        # If appointment is tomorrow - we'll set discard_after to appointment's time,
        # because it's no longer relevant after it started
        # Otherwise (if it's on a later date), we'll set it to tomorrow's midnight
        discard_after = stylist.with_salon_tz(
            min(TOMORROW_MIDNIGHT, appointment.datetime_start_at)
        )

    notification = Notification.objects.create(
        user=appointment.stylist.user, target=target, code=code,
        message=message,
        discard_after=discard_after,
        send_time_window_start=send_time_window_start,
        send_time_window_end=send_time_window_end,
        send_time_window_tz=stylist.salon.timezone,
        data={
            'appointment_datetime_start_at': appointment.datetime_start_at.isoformat(),
            'appointment_uuid': str(appointment.uuid)
        }
    )
    appointment.stylist_new_appointment_notification = notification
    appointment.stylist_new_appointment_notification_sent_at = current_now
    appointment.save(
        update_fields=[
            'stylist_new_appointment_notification',
            'stylist_new_appointment_notification_sent_at'
        ]
    )
    return 1


@transaction.atomic
def generate_tomorrow_appointments_notifications(dry_run=False) -> int:
    """
    Generate notifications about tomorrow appointments

    We're going to generate this for the stylist, for whom in their local timezone
    it's 30 minutes past their work day (or 30 minutes past 19:00, if today is not working day)

    Stylist must have at least one appointment in NEW status for tomorrow, and there
    must be no previously sent notification. If current settings for this notification imply
    that it's a push-only notification - at least one push-enabled device must be configured

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.TOMORROW_APPOINTMENTS
    message = 'You have new appointments tomorrow. Tap to see the list.'
    target = UserRole.STYLIST

    eligible_stylists_raw_queryset = Stylist.objects.raw(
        """
        select
            st_id as id
        from
            (
            select
                st_id,
                u_id,
                -- current date in stylist's timezone
                stylist_current_date_d,
                -- current time in stylist's timezone
                stylist_current_time_t,
                -- datetime of today's midnight (the one which is tonight) in stylist's timezone
                ((stylist_current_date_d + time '00:00') + interval '1 day')
                    at time zone stylist_timezone stylist_tomorrow_start_dt,
                -- datetime of tomorrow's midnight (i.e. the one which is tomorrow's tonight)
                ((stylist_current_date_d + time '00:00') + interval '2 days')
                    at time zone stylist_timezone stylist_tomorrow_end_dt,
                -- time of today's work day end. If stylist's availability is set and it's not
                -- special unavailable day - it will be set to
                -- (end of day + grace_end_day_interval_int).
                -- Otherwise it will be set to (19:00 + grace_end_day_interval_int)
                (coalesce(
                   wd.work_end_at,
                   time %(fallback_work_end_time)s) +
                     interval '%(grace_end_day_interval_int)s minutes')
                stylist_work_day_end_with_grace_period_t
            from
                (
                select
                    st.id st_id,
                    u.id u_id,
                    -- stylist's timezone as string
                    sl.timezone stylist_timezone,
                    -- current time in stylist's timezone
                    cast(
                      timestamptz %(current_now_with_tz)s at time zone sl.timezone as time
                      ) stylist_current_time_t,
                    -- current date in stylist's timezone
                    cast(
                      timestamptz %(current_now_with_tz)s at time zone sl.timezone as date
                      ) stylist_current_date_d,
                    -- current iso weekday based on date in stylist's timezone
                    extract(ISODOW
                from
                    timestamptz %(current_now_with_tz)s at time zone sl.timezone)
                      stylist_current_weekday
                from
                    stylist as st
                inner join public.user as u on
                    st.user_id = u.id
                inner join salon as sl on
                    st.salon_id = sl.id
                where
                    st.deactivated_at isnull
                order by
                    st.id ) as stylists_with_tz_aware_info
            left outer join stylist_available_day as wd on
                wd.stylist_id = st_id
                and wd.weekday = stylist_current_weekday
                and wd.is_available = true
                -- if special unavailability is set - it overrides weekday availability
                and not exists(
                  select 1 from stylist_special_available_date ssad
                  where
                    ssad.date = stylist_current_date_d
                    and ssad.stylist_id = st_id
                    and ssad.is_available = false
                )
            ) as stylists_for_whom_it_is_time_to_send
        where
            -- current time must be > stylist's work day end (real or implied) + grace period
            stylist_current_time_t > stylist_work_day_end_with_grace_period_t
            -- at least one appointment in NEW status must exist for tomorrow
            and exists(
            select 1 from appointment
            where
                stylist_id = st_id
                and datetime_start_at >= stylist_tomorrow_start_dt
                and datetime_start_at < stylist_tomorrow_end_dt
                and status = %(appointment_status)s )
            -- no notification is created for tomorrow yet
            and not exists(
            select 1 from notification
            where
                user_id = u_id
                and code = %(code)s
                and target = %(target)s
                and data->'date' ? cast(
                  cast((stylist_current_date_d + interval '1 day'
                  ) as date) as text)
              )
            and (
            -- if it's push-only notification - there should be at least 1 device
              %(not_push_only)s or
                exists(
                    select 1
                    from push_notifications_apnsdevice
                    where
                      active = true
                      and user_id = u_id
                      and application_id in (%(local_apns_id)s, %(server_apns_id)s)
                )
                or exists(
                     select 1
                     from push_notifications_gcmdevice
                     where
                       active = true
                       and user_id = u_id
                       and application_id=%(fcm_app_id)s
                )
            )
            ;
        """,
        {
            'current_now_with_tz': timezone.now().isoformat(),
            'code': code,
            'appointment_status': AppointmentStatus.NEW,
            'fallback_work_end_time': datetime.time(19, 0).isoformat(),
            'grace_end_day_interval_int': 30,
            'target': UserRole.STYLIST,
            'not_push_only': str(not is_push_only(code)),
            'local_apns_id': MobileAppIdType.IOS_STYLIST_DEV,
            'server_apns_id': MobileAppIdType.IOS_STYLIST,
            'fcm_app_id': MobileAppIdType.ANDROID_STYLIST
        }
    )
    # we can't operate directy on RawQuerySet, so we have to extract eligible ids out
    # of it

    eligible_stylist_ids = [
        stylist.id for stylist in eligible_stylists_raw_queryset]
    eligible_stylists = Stylist.objects.filter(id__in=eligible_stylist_ids)
    notifications_to_create_list: List[Notification] = []

    for stylist in eligible_stylists.select_for_update(skip_locked=True):
        # we can safely set start time window to now, since we've verified the condition
        # in the main query
        current_now: datetime.datetime = stylist.with_salon_tz(
            timezone.now()
        )
        send_time_window_start = current_now.time()
        send_time_window_end = datetime.time(23, 59, 59)
        send_time_window_tz = stylist.salon.timezone
        tomorrow_date_iso_str: str = (
            current_now.date() + datetime.timedelta(days=1)
        ).isoformat()

        # set discard_after to today's midnight in stylist's timezone
        discard_after = stylist.salon.timezone.localize(
            datetime.datetime.combine(
                current_now.date(), datetime.time(0, 0)
            )
        ) + datetime.timedelta(days=1)

        notifications_to_create_list.append(
            Notification(
                user=stylist.user,
                code=code,
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=send_time_window_tz,
                discard_after=discard_after,
                data={'date': tomorrow_date_iso_str}
            )
        )
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_client_registration_incomplete_notifications(dry_run=False) -> int:
    code = NotificationCode.CLIENT_REGISTRATION_INCOMPLETE
    discard_after = timezone.now() + datetime.timedelta(days=30)
    message = (
        'Want to get the best promotion in town? Tap now to complete your profile!'
    )
    one_day_ago = (timezone.now() - datetime.timedelta(days=1))
    target = UserRole.CLIENT
    send_time_window_start = datetime.time(11, 0)
    send_time_window_end = datetime.time(18, 0)

    client_has_recent_notification_subquery = Notification.objects.filter(
        Q(Q(sent_at__gte=one_day_ago) | Q(pending_to_send=True)),
        user_id=OuterRef('user__id'), target=target,
    )

    client_has_same_notifications_subquery = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=target, code=code)
    eligible_clients_ids = Client.objects.filter(
        created_at__lte=one_day_ago,
        profile_completeness__lt=1,
    ).annotate(
        client_has_same_notifications=Exists(client_has_same_notifications_subquery),
        client_has_recent_notification=Exists(client_has_recent_notification_subquery),
    ).filter(
        client_has_same_notifications=False,
        client_has_recent_notification=False
    ).values_list('id', flat=True)

    if is_push_only(code):
        client_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_clients_ids = eligible_clients_ids.filter(
            client_has_registered_devices
        )

    eligible_clients = Client.objects.filter(
        id__in=eligible_clients_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []
    for client in eligible_clients.iterator():
        send_time_window_tz = pytz.timezone(settings.TIME_ZONE)

        notifications_to_create_list.append(
            Notification(
                user=client.user,
                code=code,
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=send_time_window_tz,
                discard_after=discard_after,
            )
        )
    # if any notifications were generated - bulk create them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_stylist_registration_incomplete_notifications(dry_run=False) -> int:
    """
    Generate registration_incomplete notifications for stylists after 24 hours
    since registration start if registration is not complete. Send immediately
    if current time in [11am..6pm] in stylist’s timezone otherwise delay until
    next [11am..6pm] window.

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.REGISTRATION_INCOMPLETE
    discard_after = timezone.now() + datetime.timedelta(days=30)
    message = (
        'We noticed that you have not completed your registration. Once you '
        'finish all registration steps clients will be able to find and book '
        'appointments with you.'
    )
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(11, 0)
    send_time_window_end = datetime.time(18, 0)

    # select all stylists with incomplete registration, for whom local time is < 6pm
    # in their local timezone. Unfortunately, due to existing flaw in our DB structure
    # some of the stylists with incomplete registration may not have a salon, so
    # we cannot extract timezone information for such stylists; we'll assume EST for
    # them
    # We should also omit stylists who already have this notification, and if this
    # notification is push-only - we should also omit stylists without push-enabled
    # devices

    # incomplete registration is defined as in is_profile_bookable and is at least one
    # of the following criteria:
    #  - user phone is not set
    #  - business hours not set
    #  - no enabled services
    eligible_stylists_raw_queryset = Stylist.objects.raw(
        """
        select
            stylist_id id,
            u_id,
            stylist_current_now_t,
            stylist_maximum_time_to_send_today_t,
            time_since_creation
        from
            (
            select
                st.user_id u_id,
                st.id stylist_id,
                st.created_at stylist_created_at_dt,
                cast(timestamptz %(current_timestamp_tz)s at time zone coalesce(sl.timezone,
                %(default_timezone)s) as time) stylist_current_now_t,
                time %(maximum_evening_time)s stylist_maximum_time_to_send_today_t,
                (timestamptz %(current_timestamp_tz)s - st.created_at) time_since_creation,
                u.phone phone,
                st.has_business_hours_set has_business_hours_set
            from
                stylist as st
            inner join public.user as u on st.user_id = u.id
            left outer join salon as sl on
                st.salon_id = sl.id
            where st.deactivated_at isnull and u.phone is not null and u.phone <> ''
            ) as stylist_with_tz_info
        where
            stylist_current_now_t < stylist_maximum_time_to_send_today_t
            and (
              has_business_hours_set is false
              or not exists(
                select 1 from stylist_service as ss
                 where ss.stylist_id = stylist_id
                        and ss.is_enabled = True
                  )
            )
            and time_since_creation > interval '3 days'
            and not exists(
                select
                    1
                from
                    notification
                where
                    user_id = u_id
                    and code = %(code)s
                    and target = %(target)s )
            and (%(not_push_only)s
            or exists(
                select
                    1
                from
                    push_notifications_apnsdevice
                where
                    active = true
                    and user_id = u_id
                    and application_id in (%(local_apns_id)s, %(server_apns_id)s)
                )
            or exists(
                select
                    1
                from
                    push_notifications_gcmdevice
                where
                    active = true
                    and user_id = u_id
                    and application_id = %(fcm_app_id)s )
                )
          ;
        """,
        {
            'current_timestamp_tz': timezone.now().isoformat(),
            'maximum_evening_time': datetime.time(18, 00).isoformat(),
            'default_timezone': settings.TIME_ZONE,
            'code': code,
            'target': UserRole.STYLIST,
            'not_push_only': str(not is_push_only(code)),
            'local_apns_id': MobileAppIdType.IOS_STYLIST_DEV,
            'server_apns_id': MobileAppIdType.IOS_STYLIST,
            'fcm_app_id': MobileAppIdType.ANDROID_STYLIST
        }
    )
    # we can't operate directly on RawQuerySet, so we have to extract eligible ids out
    # of it
    eligible_stylist_ids = [
        stylist.id for stylist in eligible_stylists_raw_queryset]

    eligible_stylists = Stylist.objects.filter(id__in=eligible_stylist_ids)
    notifications_to_create_list: List[Notification] = []
    for stylist in eligible_stylists.select_for_update(skip_locked=True):
        send_time_window_tz = pytz.timezone(settings.TIME_ZONE)
        if stylist.salon:
            send_time_window_tz = stylist.salon.timezone

        notifications_to_create_list.append(
            Notification(
                user=stylist.user,
                code=code,
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=send_time_window_tz,
                discard_after=discard_after,
            )
        )
    # if any notifications were generated - bulk create them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_remind_define_services_notification(dry_run=False) -> int:
    """
    Notification to remind stylist to add the services

    Window start: Immediately if current time in [10am..8pm] in stylist’s timezone
    otherwise delay until next 10am.

    Window end: 20:00

    Discard after: Now+7days
    :param dry_run:if set to True, don't actually create notifications
    :return:number of notifications created
    """
    code = NotificationCode.REMIND_DEFINE_SERVICES
    discard_after = timezone.now() + datetime.timedelta(days=7)
    message = (
        "Don't forget! Update your services and pricing in Made Pro so clients can start booking."
    )
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(10, 0, 0)
    send_time_window_end = datetime.time(20, 0, 0)
    one_day_ago = (timezone.now() - datetime.timedelta(days=1))
    earliest_time_stylist_created_profile = (timezone.now() - datetime.timedelta(days=20))
    earliest_time_same_notification_sent = (timezone.now() - datetime.timedelta(days=7))

    # **Filter Conditions**
    # -Stylist account is not partial, it is a full profile
    # -stylist services are not yet defined
    # -Stylist created account less than 30 days ago
    # -remind_define_services notification was never sent to this stylist
    # -there are no pending notifications
    # -24 hours or more passed since last notification of any type was sent

    stylist_has_services = StylistService.objects.filter(
        stylist_id=OuterRef('id'), is_enabled=True
    )
    stylist_has_prior_notifications = Notification.objects.filter(
        user_id=OuterRef('user__id'), code=code, target=UserRole.STYLIST
    )
    stylist_has_recent_notification = Notification.objects.filter(
        Q(Q(sent_at__gte=one_day_ago) | Q(pending_to_send=True)),
        user_id=OuterRef('user__id'), target=UserRole.STYLIST,
    )
    stylist_has_same_notification_query = Notification.objects.filter(
        user_id=OuterRef('user__id'), code=code, target=UserRole.STYLIST,
        created_at__gte=earliest_time_same_notification_sent
    )

    eligible_stylists_ids = Stylist.objects.filter(
        deactivated_at__isnull=True,
        created_at__gte=earliest_time_stylist_created_profile,
        created_at__lte=one_day_ago,
    ).exclude(
        Q(user__phone__isnull=True) | Q(user__phone__exact='')
    ).annotate(
        stylist_has_services=Exists(stylist_has_services),
        client_has_prior_notifications=Exists(stylist_has_prior_notifications),
        client_has_recent_notification=Exists(stylist_has_recent_notification),
        has_same_notification=Exists(stylist_has_same_notification_query),
    ).filter(
        stylist_has_services=False,
        client_has_prior_notifications=False,
        has_same_notification=False,
        client_has_recent_notification=False
    ).values_list('id', flat=True)

    if is_push_only(code):
        stylist_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_stylists_ids = eligible_stylists_ids.filter(
            stylist_has_registered_devices
        )

    eligible_stylists = Stylist.objects.filter(
        id__in=eligible_stylists_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []
    for stylist in eligible_stylists.iterator():
        send_time_window_tz = stylist.salon.timezone

        notifications_to_create_list.append(
            Notification(
                user=stylist.user,
                code=code,
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=send_time_window_tz,
                discard_after=discard_after,
            )
        )
    # if any notifications were generated - bulk create them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_remind_invite_clients_notifications(dry_run=False) -> int:
    """
    Generate `remind_invite_clients` notifications for stylist matching the criteria:
    1. Stylist did not invite any clients ever.
    2. 24 hours or more passed since last notification of any type was sent
       to this stylist and there are no pending notifications.
    3. remind_invite_clients notification was never sent or was sent more than 30 days
       ago last time to this stylist
    4. Stylist created account less than 90 days ago.
    5. Stylist is bookable (has defined hours, services).
    6. Stylist account is not partial, it is a full profile.

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.REMIND_INVITE_CLIENTS
    discard_after = timezone.now() + datetime.timedelta(days=7)
    message = (
        'We noticed that you have not invited any clients to Made Pro. Stylists who '
        'invite 10 or more clients usually get their first booking within 24 hours.'
    )

    earliest_time_stylist_created_profile = timezone.now() - datetime.timedelta(days=79)
    one_day_ago = timezone.now() - datetime.timedelta(hours=24)
    earliest_time_same_notification_sent = timezone.now() - datetime.timedelta(days=20)
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(10, 0)
    send_time_window_end = datetime.time(20, 0)

    stylist_has_invitations_query = Invitation.objects.filter(
        stylist_id=OuterRef('id'), invite_target=UserRole.CLIENT.value
    )
    stylist_has_notifications_sent_within_24hours_query = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=UserRole.STYLIST, sent_at__isnull=False,
        sent_at__gte=one_day_ago
    )
    stylist_has_any_pending_notifications_query = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=UserRole.STYLIST, pending_to_send=True
    )
    stylist_has_same_notification_query = Notification.objects.filter(
        user_id=OuterRef('user__id'), code=code, target=UserRole.STYLIST,
        created_at__gte=earliest_time_same_notification_sent
    )

    stylist_has_enabled_services_query = StylistService.objects.filter(
        stylist_id=OuterRef('id'), is_enabled=True
    )
    eligible_stylists_ids = Stylist.objects.annotate(
        has_invitations=Exists(stylist_has_invitations_query),
        has_notifications_within_24hours=Exists(
            stylist_has_notifications_sent_within_24hours_query
        ),
        has_any_pending_notifications=Exists(stylist_has_any_pending_notifications_query),
        has_same_notification=Exists(stylist_has_same_notification_query),
        has_enabled_services=Exists(stylist_has_enabled_services_query),
    ).filter(
        has_invitations=False,
        has_notifications_within_24hours=False,
        has_any_pending_notifications=False,
        has_same_notification=False,
        has_enabled_services=True,
        created_at__gte=earliest_time_stylist_created_profile,
        created_at__lte=one_day_ago,
        user__phone__isnull=False,
        deactivated_at__isnull=True,
    ).values_list('id', flat=True)

    if is_push_only(code):
        stylist_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_stylists_ids = eligible_stylists_ids.filter(
            stylist_has_registered_devices
        )

    eligible_stylists = Stylist.objects.filter(
        id__in=eligible_stylists_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []

    for stylist in eligible_stylists.iterator():
        short_name = stylist.get_short_name()
        unsubscribe_url = get_unsubscribe_url(target, stylist.uuid)
        msg_plain = render_to_string('email/notification/remind_invite_clients/body.txt',
                                     {'short_name': short_name,
                                      'unsubscribe_url': unsubscribe_url})
        msg_html = render_to_string('email/notification/remind_invite_clients/body.html',
                                    {'short_name': short_name, 'unsubscribe_url': unsubscribe_url})
        mail_subject = render_to_string('email/notification/remind_invite_clients/subject.txt',
                                        {'short_name': short_name})

        notifications_to_create_list.append(
            Notification(
                user=stylist.user,
                code=code,
                email_details={
                    'from': settings.DEFAULT_FROM_EMAIL,
                    'to': stylist.email,
                    'subject': mail_subject,
                    'text_content': msg_plain,
                    'html_content': msg_html
                },
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=stylist.salon.timezone,
                discard_after=discard_after,
                data={}
            )
        )
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_remind_add_photo_notifications(dry_run=False) -> int:
    """
    Generate `remind_add_photo` notifications for stylist matching the criteria:
    1. Stylist did not invite any clients ever.
    2. 24 hours or more passed since last notification of any type was sent
       to this stylist and there are no pending notifications.
    3. remind_add_photo notification was never sent
    4. Stylist created account less than 59 days ago.
    5. Stylist is bookable (has defined hours, services).
    6. Stylist account is not partial, it is a full profile.
    7. Stylist doesnot have a photo

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.REMIND_ADD_PHOTO
    discard_after = timezone.now() + datetime.timedelta(days=7)
    message = (
        'We noticed that you do not have a photo in Made Pro. Stylists who '
        'have a photo have on average about 60% higher chance to get a booking.'
    )
    earliest_time_stylist_created_profile = timezone.now() - datetime.timedelta(days=59)
    one_day_ago = timezone.now() - datetime.timedelta(hours=24)
    earliest_time_same_notification_sent = timezone.now() - datetime.timedelta(days=15)
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(10, 0)
    send_time_window_end = datetime.time(20, 0)

    stylist_has_invitations_query = Invitation.objects.filter(
        stylist_id=OuterRef('id'), invite_target=UserRole.CLIENT.value
    )
    stylist_has_recent_or_unsent_notifications = Notification.objects.filter(
        Q(Q(sent_at__gte=one_day_ago) | Q(pending_to_send=True)),
        user_id=OuterRef('user__id'), target=UserRole.STYLIST
    )

    stylist_has_remind_add_photo_notification_sent = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=UserRole.STYLIST, code=code,
        created_at__gte=earliest_time_same_notification_sent
    )

    stylist_has_enabled_services_query = StylistService.objects.filter(
        stylist_id=OuterRef('id'), is_enabled=True
    )
    eligible_stylists_ids = Stylist.objects.annotate(
        has_invitations=Exists(stylist_has_invitations_query),
        has_recent_or_unsent_notifications=Exists(
            stylist_has_recent_or_unsent_notifications
        ),
        has_remind_add_photo_notification_sent=Exists(
            stylist_has_remind_add_photo_notification_sent
        ),
        has_enabled_services=Exists(stylist_has_enabled_services_query),
    ).filter(
        Q(Q(user__photo='') | Q(user__photo=None)),
        has_invitations=False,
        has_recent_or_unsent_notifications=False,
        has_remind_add_photo_notification_sent=False,
        has_enabled_services=True,
        created_at__gte=earliest_time_stylist_created_profile,
        created_at__lte=one_day_ago,
        user__phone__isnull=False,
        deactivated_at__isnull=True,
    ).values_list('id', flat=True)

    if is_push_only(code):
        stylist_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_stylists_ids = eligible_stylists_ids.filter(
            stylist_has_registered_devices
        )

    eligible_stylists = Stylist.objects.filter(
        id__in=eligible_stylists_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []

    for stylist in eligible_stylists.iterator():
        notifications_to_create_list.append(
            Notification(
                user=stylist.user,
                code=code,
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=stylist.salon.timezone,
                discard_after=discard_after,
                data={}
            )
        )
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_remind_define_discounts_notifications(dry_run=False) -> int:
    """
    Generate `remind_define_discounts` notifications for stylist matching the criteria:
    1. Stylist discounts are not yet defined
    2. 24 hours or more passed since last notification of any type was sent to this stylist
        and there are no pending notifications.
    3. remind_define_discounts notification was never sent to this stylist
    4. Stylist created account less than 90 days ago.
    5. Stylist is bookable (has defined hours, services).
    6. Stylist account is not partial, it is a full profile.
    7. N - number of clients in the nearby area is > 0. N is calculated as number of clients
        that are within 100 miles radius from salon.

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.REMIND_DEFINE_DISCOUNTS
    discard_after = timezone.now() + datetime.timedelta(days=7)
    message_template = (
        '{0} clients in your area are looking for the best deals. '
        'Don\'t forget to update your discounts to get the most out of Made Pro!'
    )
    earliest_time_stylist_created_profile = timezone.now() - datetime.timedelta(days=90)
    one_day_ago = timezone.now() - datetime.timedelta(hours=24)
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(10, 0)
    send_time_window_end = datetime.time(20, 0)

    stylist_has_recent_or_unsent_notifications = Notification.objects.filter(
        Q(Q(sent_at__gte=one_day_ago) | Q(pending_to_send=True)),
        user_id=OuterRef('user__id'), target=UserRole.STYLIST
    )

    stylist_has_remind_define_discounts_notification_sent = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=UserRole.STYLIST, code=code
    )

    stylist_has_enabled_services_query = StylistService.objects.filter(
        stylist_id=OuterRef('id'), is_enabled=True
    )
    eligible_stylists_ids = Stylist.objects.annotate(
        has_recent_or_unsent_notifications=Exists(
            stylist_has_recent_or_unsent_notifications
        ),
        has_remind_define_discounts_notification_sent=Exists(
            stylist_has_remind_define_discounts_notification_sent
        ),
        has_enabled_services=Exists(stylist_has_enabled_services_query),
    ).filter(
        salon__location__isnull=False,
        is_discount_configured=False,
        has_recent_or_unsent_notifications=False,
        has_remind_define_discounts_notification_sent=False,
        created_at__gte=earliest_time_stylist_created_profile,
        created_at__lte=one_day_ago,
        has_enabled_services=True,
        user__phone__isnull=False,
        deactivated_at__isnull=True,
    ).values_list('id', flat=True)

    if is_push_only(code):
        stylist_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_stylists_ids = eligible_stylists_ids.filter(
            stylist_has_registered_devices
        )

    eligible_stylists = Stylist.objects.filter(
        id__in=eligible_stylists_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []

    for stylist in eligible_stylists.iterator():
        nearby_clients_count = Client.objects.filter(
            country__iexact=stylist.salon.country,
            location__distance_lte=(stylist.salon.location, D(m=160934))).count()
        if nearby_clients_count:
            notifications_to_create_list.append(
                Notification(
                    user=stylist.user,
                    code=code,
                    target=target,
                    message=message_template.format(nearby_clients_count),
                    send_time_window_start=send_time_window_start,
                    send_time_window_end=send_time_window_end,
                    send_time_window_tz=stylist.salon.timezone,
                    discard_after=discard_after,
                    data={}
                )
            )
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_follow_up_invitation_sms(dry_run=False) -> int:
    """
    If there is an invitation to a client that is not accepted and the client
    phone number does not have an account with us send a follow up text message
    14 day after original invitation is sent.
    :param dry_run:
    :param dry_run: if set to True, don't actually create notifications
    :return: number of SMS messages sent
    """
    message = (
        'Hey! Just following up on the invite {inviter_name} '
        'sent you about booking on MADE. You see better prices when you book '
        '{stylist_mention}there. Download the app at: https://madebeauty.com/get/'
    )
    earliest_invitation_creation_datetime = timezone.now() - datetime.timedelta(days=60)
    earliest_time_invitation_sent = timezone.now() - datetime.timedelta(days=14)
    send_time_window_tz = pytz.timezone(settings.TIME_ZONE)

    send_time_window_start = datetime.time(18, 0)
    send_time_window_end = datetime.time(20, 0)

    current_now = timezone.now().astimezone(send_time_window_tz)
    if current_now.time() < send_time_window_start or current_now.time() > send_time_window_end:
        return 0

    # we want to send SMS's in chunks to not overload Twilio and Slack
    max_sms_messages_to_send_in_one_run = 20
    invitation_author = Q(stylist__isnull=False) | Q(invited_by_client__isnull=False)
    eligible_invites = Invitation.objects.filter(
        Q(invitation_author),
        created_client__isnull=True,
        followup_sent_at__isnull=True,
        created_at__lte=earliest_time_invitation_sent,
        created_at__gte=earliest_invitation_creation_datetime,
        status=InvitationStatus.INVITED,
        invite_target=UserRole.CLIENT,
    ).select_for_update(skip_locked=True)[:max_sms_messages_to_send_in_one_run]

    sent_messages = 0

    for invite in eligible_invites.iterator():
        invitation_author = invite.stylist if invite.stylist else invite.invited_by_client
        invitation_author_user: User = invitation_author.user
        invitation_author_name = invitation_author_user.first_name
        if not invitation_author_name:
            invitation_author_name = invitation_author_user.get_full_name()
        stylist_mention = 'with {inviter_name} '.format(
            inviter_name=invitation_author_name
        ) if invite.stylist else ''
        message = message.format(
            inviter_name=invitation_author_name,
            stylist_mention=stylist_mention
        )
        try:
            if not dry_run:
                send_sms_message(to_phone=invite.phone, body=message, role=UserRole.CLIENT)
                invite.followup_sent_at = timezone.now()
                invite.followup_count += 1
                invite.save(update_fields=['followup_sent_at', 'followup_count', ])
            sent_messages += 1
        except:  # noqa
            # something went wrong here. We're in the outermost transaction, so just
            # log the error and move on
            logger.exception('Could not send SMS to {0}. Exiting'.format(invite.phone))
            break
    return sent_messages


@transaction.atomic
def generate_remind_define_hours_notifications(dry_run=False) -> int:
    """
    Generate `remind_define_hours` notifications for stylist matching the criteria:
    1. Stylist working hours are not yet defined
    2. 24 hours or more passed since last notification of any type was sent to this
        stylist and there are no pending notifications.
    3. remind_define_hours notification was never sent to this stylist
    4. Stylist created account less than 30 days ago.
    5. Stylist account is not partial, it is a full profile.

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.REMIND_DEFINE_HOURS
    discard_after = timezone.now() + datetime.timedelta(days=7)
    message = (
        "Don't forget! Update your hours in Made Pro so clients can start booking."
    )
    earliest_time_stylist_created_profile = timezone.now() - datetime.timedelta(days=30)
    one_day_ago = timezone.now() - datetime.timedelta(hours=24)
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(10, 0)
    send_time_window_end = datetime.time(20, 0)

    stylist_has_recent_or_unsent_notifications = Notification.objects.filter(
        Q(Q(sent_at__gte=one_day_ago) | Q(pending_to_send=True)),
        user_id=OuterRef('user__id'), target=UserRole.STYLIST
    )

    stylist_has_remind_define_hours_notification_sent = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=UserRole.STYLIST, code=code
    )

    eligible_stylists_ids = Stylist.objects.annotate(
        has_recent_or_unsent_notifications=Exists(
            stylist_has_recent_or_unsent_notifications
        ),
        has_remind_define_hours_notification_sent=Exists(
            stylist_has_remind_define_hours_notification_sent
        ),
    ).filter(
        has_recent_or_unsent_notifications=False,
        has_remind_define_hours_notification_sent=False,
        created_at__gte=earliest_time_stylist_created_profile,
        created_at__lte=one_day_ago,
        user__phone__isnull=False,
        deactivated_at__isnull=True,
        has_business_hours_set=False,
    ).values_list('id', flat=True)
    if is_push_only(code):
        stylist_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_stylists_ids = eligible_stylists_ids.filter(
            stylist_has_registered_devices
        )

    eligible_stylists = Stylist.objects.filter(
        id__in=eligible_stylists_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []

    for stylist in eligible_stylists.iterator():
        notifications_to_create_list.append(
            Notification(
                user=stylist.user,
                code=code,
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=stylist.salon.timezone,
                discard_after=discard_after,
                data={}
            )
        )
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_deal_of_week_notifications(dry_run=False) -> int:
    """
    Generate `deal_of_week` notifications for clients matching the criteria:
    1. there is a stylist within 10 miles radius from client's zipcode and this
      stylist has a "deal of the week" in 1..2 days from today.
    2. Last notification of this type was sent more than 4 weeks ago to this client
    3. Last notification of any type was sent more than 24 hours ago to this client
    4. Stylist should be generally bookable

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.DEAL_OF_THE_WEEK
    target = UserRole.CLIENT
    send_time_window_start = datetime.time(11, 0)
    send_time_window_end = datetime.time(18, 0)
    message = (
        'Great news, {stylist_name} on Made has added a "Deal of the Week" on '
        '{weekday} with {deal_percent}% discount! Check them out in Made app.'
    )

    minimum_distance_miles = 10
    minimum_distance_meters = minimum_distance_miles * 1609

    eligible_clients_queryset = Client.objects.raw(
        '''
  SELECT
    DISTINCT ON (id)
    id,
    client_user_id,
    stylist_first_name,
    stylist_uuid,
    deal_percent,
    deal_weekday,
    days_before_discount,
    salon_timezone
  FROM (
     SELECT
       *,
       CASE WHEN deal_weekday > current_weekday
         THEN deal_weekday - current_weekday
       ELSE deal_weekday - current_weekday + 7
       END days_before_discount
     FROM (
        SELECT
          cl.id id,
          cu.id client_user_id,
          swd.weekday deal_weekday,
          swd.discount_percent deal_percent,
          ST_DISTANCE(sl.location, cl.location) distance,
          extract(
             ISODOW FROM TIMESTAMPTZ %(current_now_with_tz)s
             AT TIME ZONE sl.timezone) current_weekday,
          su.first_name stylist_first_name,
          st.uuid stylist_uuid,
          sl.timezone salon_timezone,
          sad.is_available
        FROM
          public.client cl
          INNER JOIN public.preferred_stylist ps ON ps.client_id = cl.id
          INNER JOIN public.stylist st ON ps.stylist_id = st.id
          INNER JOIN public.user cu ON cu.id = cl.user_id
          INNER JOIN public.user su ON su.id = st.user_id
          INNER JOIN public.salon sl ON sl.id = st.salon_id
          LEFT OUTER JOIN public.stylist_weekday_discount swd ON swd.stylist_id = st.id
          LEFT OUTER JOIN public.stylist_available_day sad ON sad.stylist_id = st.id AND
                                                              sad.weekday = swd.weekday
        WHERE
          ps.deleted_at ISNULL AND
          -- stylist is generally bookable
          su.phone IS NOT NULL AND
          EXISTS(SELECT 1
                 FROM public.stylist_service
                 WHERE cu.is_active IS TRUE AND stylist_service.stylist_id = st.id) AND
          -- deal of the week is defined
          swd.is_deal_of_week = TRUE AND
          swd.discount_percent > 0 AND
          -- locations of stylist and client are known
          sl.location IS NOT NULL AND
          cl.location IS NOT NULL AND
          sad.is_available IS TRUE AND
          -- no previous notification was sent in the last 24 hours
          NOT EXISTS(SELECT 1
                     FROM public.notification
                     WHERE user_id = cu.id AND
                           target = %(target)s AND
                           code != %(code)s AND
                           ((TIMESTAMPTZ %(current_now_with_tz)s
                           AT TIME ZONE sl.timezone) - created_at) <=
                           INTERVAL '24 hours')
          AND
          -- no notification of the same type was sent in the last 4 weeks
          NOT EXISTS(SELECT 1
                     FROM public.notification
                     WHERE user_id = cu.id AND
                           target = %(target)s AND
                           code = %(code)s AND
                           ((TIMESTAMPTZ %(current_now_with_tz)s
                           AT TIME ZONE sl.timezone) - created_at) <=
                           INTERVAL '4 weeks')
          ) main
     WHERE distance < %(minimum_distance_meters)s
     FOR UPDATE SKIP LOCKED
   ) main_with_time_diff
  WHERE
    days_before_discount BETWEEN 1 AND 2
  ORDER BY
    id, days_before_discount
      ''',
        {
            'current_now_with_tz': timezone.now().isoformat(),
            'minimum_distance_meters': minimum_distance_meters,
            'code': code,
            'target': target

        }
    )
    notifications_to_create_list: List[Notification] = []
    for client in eligible_clients_queryset:
        salon_timezone = pytz.timezone(client.salon_timezone)
        current_salon_date = timezone.now().astimezone(salon_timezone).date()
        current_weekday = current_salon_date.isoweekday()
        deal_weekday = client.deal_weekday
        days_delta = deal_weekday - current_weekday
        if days_delta < 0:
            days_delta += 7
        deal_date = current_salon_date + datetime.timedelta(days=days_delta)
        deal_weekday_str = deal_date.strftime('%A')
        message = message.format(
            stylist_name=client.stylist_first_name,
            weekday=deal_weekday_str,
            deal_percent=client.deal_percent
        )
        discard_after = salon_timezone.localize(
            datetime.datetime.combine(
                deal_date,
                datetime.time(0, 0)
            )
        )
        notifications_to_create_list.append(
            Notification(
                user_id=client.client_user_id,
                code=code,
                target=target,
                message=message,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=salon_timezone,
                discard_after=discard_after,
                data={
                    'stylist_uuid': str(client.stylist_uuid),
                    'deal_weekday': client.deal_weekday,
                    'deal_date': deal_date.isoformat()
                }
            )
        )
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


@transaction.atomic
def generate_invite_your_stylist_notifications(dry_run=False) -> int:
    """
    Generate `invite_your_stylist` notifications for clients matching the criteria:
    1. Client has no preferred stylist
    2. Client has registered no more than 90 days ago
    3. Last notification of this type was sent more than 4 weeks ago to this client
    4. Last notification of any type was sent more than 24 hours ago to this client

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.INVITE_YOUR_STYLIST
    target = UserRole.CLIENT
    send_time_window_start = datetime.time(11, 0)
    send_time_window_end = datetime.time(18, 0)
    earliest_time_client_created = timezone.now() - datetime.timedelta(days=90)
    message = (
        'Did you know you can now invite your stylist to accept appointments in Made? '
        'You can do it from the search screen in Made app.'
    )
    sms_message = (
        'Did you know you can now invite your stylist to accept appointments in Made? '
        'You can do it from the search screen in Made app.'
        'Click here to open Made app: https://madebeauty.com/get/'
    )
    notifications_to_create_list: List[Notification] = []

    client_has_prior_notifications_with_same_code_subquery = Notification.objects.filter(
        user_id=OuterRef('user__id'), code=code,
        created_at__gte=timezone.now() - datetime.timedelta(weeks=4),
        target=UserRole.CLIENT
    )

    client_has_recent_notifications_subquery = Notification.objects.filter(
        user_id=OuterRef('user__id'),
        created_at__gte=timezone.now() - datetime.timedelta(hours=24),
        target=UserRole.CLIENT
    ).exclude(code=code)
    eligible_client_ids = Client.objects.filter(
        preferred_stylists__isnull=True,
        created_at__gte=earliest_time_client_created
    ).annotate(
        client_has_prior_notifications_with_same_code=Exists(
            client_has_prior_notifications_with_same_code_subquery
        ),
        client_has_recent_notifications=Exists(client_has_recent_notifications_subquery)
    ).filter(
        client_has_prior_notifications_with_same_code=False,
        client_has_recent_notifications=False
    ).values_list('id', flat=True)

    if is_push_only(code):
        client_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_client_ids = eligible_client_ids.filter(
            client_has_registered_devices
        )
    eligible_clients_queryset = Client.objects.filter(
        id__in=eligible_client_ids
    ).select_for_update(skip_locked=True)

    for client in eligible_clients_queryset:
        client_name = client.user.get_short_name()
        short_name = '{0} '.format(client_name) if client_name else ''
        unsubscribe_url = get_unsubscribe_url(target, client.uuid)
        msg_plain = render_to_string('email/notification/invite_your_stylist/body.txt',
                                     {'short_name': short_name,
                                      'unsubscribe_url': unsubscribe_url})
        msg_html = render_to_string('email/notification/invite_your_stylist/body.html',
                                    {'short_name': short_name, 'unsubscribe_url': unsubscribe_url})
        mail_subject = render_to_string('email/notification/invite_your_stylist/subject.txt',
                                        {'short_name': short_name})

        discard_after = client.created_at + datetime.timedelta(days=90)
        notifications_to_create_list.append(
            Notification(
                user=client.user,
                code=code,
                target=target,
                message=message,
                sms_message=sms_message,
                email_details={
                    'from': settings.DEFAULT_FROM_EMAIL,
                    'to': client.email,
                    'subject': mail_subject,
                    'text_content': msg_plain,
                    'html_content': msg_html
                },
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=pytz.timezone(settings.TIME_ZONE),
                discard_after=discard_after,
                forced_channel=NotificationChannel.SMS,
                data={}
            )
        )
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)


class Unnest(Func):
    function = 'Unnest'


def get_search_appearances_per_stylist_in_past_week() -> Counter:
    search_appearence_past_days = timezone.now() - datetime.timedelta(days=7)

    stylist_ids_search_count = Counter(list(
        StylistSearchRequest.objects.filter(
            created_at__gte=search_appearence_past_days).annotate(stylists_found_ids=Unnest(
                'stylists_found', distinct=True)).values_list(
            'stylists_found_ids', flat=True)))

    return stylist_ids_search_count


@transaction.atomic
def generate_stylist_appeared_in_search_notification(dry_run=False) -> int:
    '''
    Generate the notifications to denote how many times the stylist has appeared in search
    results. The filter should match the following criteria

    1. If stylist appeared in search results in Client App more than 0 times.
       This appearance happened no more than 7 days ago
    2. Last notification of any type sent to the stylist was more than 7 days ago
    3. More than 7 days since stylist registration

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    '''
    SEND_NOTIFICATION_ONCE_IN_DAYS = 7

    code = NotificationCode.APPEARED_IN_SEARCH
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(11, 0)
    send_time_window_end = datetime.time(18, 0)
    discard_after = timezone.now() + datetime.timedelta(days=7)
    recent_same_notification_sent__before_days = timezone.now() - datetime.timedelta(
        days=SEND_NOTIFICATION_ONCE_IN_DAYS)

    message = (
        'Your name appeared in searches by Made clients {0} times '
        'since {1}.'
    )

    stylist_created_before_days = timezone.now() - datetime.timedelta(days=7)

    stylist_ids_search_count = get_search_appearances_per_stylist_in_past_week()

    stylist_has_same_notifications_recently_subquery = Notification.objects.filter(
        user_id=OuterRef('user__id'),
        created_at__gte=recent_same_notification_sent__before_days,
        target=target,
        code=code
    )

    eligible_stylists_ids = Stylist.objects.filter(
        id__in=stylist_ids_search_count.keys(),
        created_at__lte=stylist_created_before_days
    ).annotate(
        stylist_has_same_notifications_recently=Exists(
            stylist_has_same_notifications_recently_subquery),
    ).filter(
        stylist_has_same_notifications_recently=False,
    ).values_list('id', flat=True)

    if is_push_only(code):
        stylist_has_registered_devices = Q(
            user__apnsdevice__active=True) | Q(
            user__gcmdevice__active=True)
        eligible_stylists_ids = eligible_stylists_ids.filter(
            stylist_has_registered_devices
        )

    eligible_stylists = Stylist.objects.filter(
        id__in=eligible_stylists_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []
    for stylist in eligible_stylists.iterator():
        short_name = stylist.get_short_name()
        unsubscribe_url = get_unsubscribe_url(target, stylist.uuid)
        msg_plain = render_to_string('email/notification/appeared_in_search/body.txt',
                                     {'short_name': short_name, 'unsubscribe_url': unsubscribe_url,
                                      'appearance_count': stylist_ids_search_count[stylist.id],
                                      'days_since': SEND_NOTIFICATION_ONCE_IN_DAYS})
        msg_html = render_to_string('email/notification/appeared_in_search/body.html',
                                    {'short_name': short_name, 'unsubscribe_url': unsubscribe_url,
                                     'appearance_count': stylist_ids_search_count[stylist.id],
                                     'days_since': SEND_NOTIFICATION_ONCE_IN_DAYS})
        mail_subject = render_to_string('email/notification/appeared_in_search/subject.txt',
                                        {'short_name': short_name})

        notifications_to_create_list.append(
            Notification(
                user=stylist.user,
                code=code,
                target=target,
                message=message.format(
                    stylist_ids_search_count[stylist.id],
                    recent_same_notification_sent__before_days.strftime('%b %-d')),
                email_details={
                    'from': settings.DEFAULT_FROM_EMAIL,
                    'to': stylist.email,
                    'subject': mail_subject,
                    'text_content': msg_plain,
                    'html_content': msg_html
                },
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
                send_time_window_tz=stylist.salon.timezone,
                discard_after=discard_after,
            )
        )
    # if any notifications were generated - bulk create them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)
