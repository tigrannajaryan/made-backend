import datetime
from io import TextIOBase
from typing import List, Optional, Tuple

import pytz

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Q
from django.utils import timezone

from appointment.models import Appointment
from appointment.types import AppointmentStatus
from client.models import Client
from core.models import UserRole
from core.utils.phone import to_international_format
from integrations.push.types import MobileAppIdType
from integrations.push.utils import has_push_notification_device
from salon.models import (
    Invitation,
    PreferredStylist,
    Stylist,
    StylistService,
    StylistWeekdayDiscount,
)
from .models import Notification
from .settings import NOTIFICATION_CHANNEL_PRIORITY
from .types import NotificationChannel, NotificationCode


def is_push_only(code: NotificationCode) -> bool:
    """Return True if notification to be delivered ONLY via push"""
    channels: List = NOTIFICATION_CHANNEL_PRIORITY.get(code, [])
    return frozenset(channels) == frozenset([NotificationChannel.PUSH])


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
        stylist__has_business_hours_set=True,
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
        has_business_hours_set=True,
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
        has_business_hours_set=True,
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
    thirty_days_ago = (timezone.now() - datetime.timedelta(days=30))

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

    eligible_stylists_ids = Stylist.objects.filter(
        deactivated_at__isnull=True,
        created_at__gte=thirty_days_ago,
    ).exclude(
        Q(user__phone__isnull=True) | Q(user__phone__exact='')
    ).annotate(
        stylist_has_services=Exists(stylist_has_services),
        client_has_prior_notifications=Exists(stylist_has_prior_notifications),
        client_has_recent_notification=Exists(stylist_has_recent_notification),
    ).filter(
        stylist_has_services=False,
        client_has_prior_notifications=False,
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
    earliest_time_stylist_created_profile = timezone.now() - datetime.timedelta(days=90)
    earliest_time_last_notification_sent = timezone.now() - datetime.timedelta(hours=24)
    earliest_time_same_notification_sent = timezone.now() - datetime.timedelta(days=30)
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(10, 0)
    send_time_window_end = datetime.time(20, 0)

    stylist_has_invitations_query = Invitation.objects.filter(
        stylist_id=OuterRef('id')
    )
    stylist_has_notifications_sent_within_24hours_query = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=UserRole.STYLIST, sent_at__isnull=False,
        sent_at__gte=earliest_time_last_notification_sent
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
        user__phone__isnull=False,
        deactivated_at__isnull=True,
        has_business_hours_set=True,
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
def generate_remind_add_photo_notifications(dry_run=False) -> int:
    """
    Generate `remind_add_photo` notifications for stylist matching the criteria:
    1. Stylist did not invite any clients ever.
    2. 24 hours or more passed since last notification of any type was sent
       to this stylist and there are no pending notifications.
    3. remind_add_photo notification was never sent
    4. Stylist created account less than 30 days ago.
    5. Stylist is bookable (has defined hours, services).
    6. Stylist account is not partial, it is a full profile.

    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.REMIND_ADD_PHOTO
    discard_after = timezone.now() + datetime.timedelta(days=7)
    message = (
        'We noticed that you do not have a photo in Made Pro. Stylists who '
        'have a photo have on average about 60% higher chance to get a booking.'
    )
    earliest_time_stylist_created_profile = timezone.now() - datetime.timedelta(days=30)
    earliest_time_last_notification_sent = timezone.now() - datetime.timedelta(hours=24)
    target = UserRole.STYLIST
    send_time_window_start = datetime.time(10, 0)
    send_time_window_end = datetime.time(20, 0)

    stylist_has_invitations_query = Invitation.objects.filter(
        stylist_id=OuterRef('id')
    )
    stylist_has_recent_or_unsent_notifications = Notification.objects.filter(
        Q(Q(sent_at__gte=earliest_time_last_notification_sent) | Q(pending_to_send=True)),
        user_id=OuterRef('user__id'), target=UserRole.STYLIST
    )

    stylist_has_remind_add_photo_notification_sent = Notification.objects.filter(
        user_id=OuterRef('user__id'), target=UserRole.STYLIST, code=code
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
        user__phone__isnull=False,
        deactivated_at__isnull=True,
        has_business_hours_set=True,
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
