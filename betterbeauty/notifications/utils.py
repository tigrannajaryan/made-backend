import datetime
from io import TextIOBase
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from appointment.models import Appointment
from appointment.types import AppointmentStatus
from client.models import Client
from core.models import UserRole
from core.utils.phone import to_international_format
from integrations.push.types import MobileAppIdType
from integrations.push.utils import has_push_notification_device
from salon.models import PreferredStylist, Stylist
from salon.utils import has_bookable_slots_with_discounts
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
    - Client must have at least one device configured
    - Stylist is bookable and has at least one available slot in the next 7 days.
    - Stylist has a discount on at least one day/service within the next 7 days.
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
    message = 'New discounts are available with your stylist. Tap to book an appointment'

    # Get all PreferredStylist records created more than 48 hrs ago, for which
    # - client has zero appointments
    # - client doesn't have previous booking hint notifications
    # - stylist has at least one available service
    # - stylist's profile is generally bookable, i.e. has phone and business hours set

    # Since we can't use select for update on query with aggregation, we'll just take
    # the list of ids, and will make another select based on these ids

    client_has_registered_devices = Q(
        client__user__apnsdevice__active=True) | Q(
        client__user__gcmdevice__active=True)

    pref_client_stylist_records_ids = PreferredStylist.objects.filter(
        created_at__gte=cutoff_datetime,
        created_at__lte=earliest_creation_datetime
    ).annotate(
        notification_cnt=Count(
            'client__user__notification', filter=Q(
                client__user__notification__code=code
            )
        )
    ).filter(
        client__appointment__isnull=True,
        notification_cnt=0,
        stylist__services__is_enabled=True,
        stylist__user__phone__isnull=False,
        stylist__user__is_active=True,
        client__user__is_active=True,
        stylist__has_business_hours_set=True,
        stylist__deactivated_at=None,
    ).values_list('id', flat=True)

    # if based on initial settings PUSH is the one and only channel that will be used
    # let's select only those clients who actually have push-enabled devices, and
    # include others only as soon as they add a push device.
    if is_push_only(code):
        pref_client_stylist_records_ids = pref_client_stylist_records_ids.filter(
            client_has_registered_devices
        )
    # actual queryset that we can lock for update on the time of
    # notifications creation
    pref_client_stylist_record = PreferredStylist.objects.filter(
        id__in=pref_client_stylist_records_ids
    ).select_for_update(skip_locked=True)

    # go over pre-screened PreferredStylist records, saving their client
    #  and stylist records as we process them to avoid double-processing.
    # For each of the eligible stylists create new Notification object

    processed_clients_list: List[Client] = []
    stylist_bookable_status_map: Dict[Stylist, bool] = {}
    notifications_to_create_list: List[Notification] = []

    for pref_stylist_obj in pref_client_stylist_record.iterator():
        client: Client = pref_stylist_obj.client
        stylist: Stylist = pref_stylist_obj.stylist

        if client in processed_clients_list:
            continue
        processed_clients_list.append(client)

        # see if we have already calculated bookable status for this stylist; if not -
        # calculate it and save to the map. Otherwise just pick it from the map
        if stylist not in stylist_bookable_status_map.keys():
            stylist_bookable_status_map[stylist] = has_bookable_slots_with_discounts(stylist)
        if stylist_bookable_status_map[stylist]:
            notifications_to_create_list.append(Notification(
                user=client.user, target=target, code=code,
                message=message,
                discard_after=discard_after,
                send_time_window_start=send_time_window_start,
                send_time_window_end=send_time_window_end,
            ))

    assert len(notifications_to_create_list) <= len(processed_clients_list)

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
        'We have {0} stylists available for booking. Tap to see them.'
    )
    client_has_registered_devices = Q(
        user__apnsdevice__active=True) | Q(
        user__gcmdevice__active=True)

    client_does_not_have_preferred_stylists = Q(
        preferred_stylists__deleted_at__isnull=False
    ) | Q(preferred_stylists__isnull=True)

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

    message = message.format(bookable_stylists.count())
    eligible_clients_ids = Client.objects.filter(
        client_does_not_have_preferred_stylists,
        created_at__lt=client_joined_before_datetime,
        created_at__gte=cutoff_datetime,
        user__is_active=True,
        # TODO: add is_active=True
    ).annotate(
        notification_cnt=Count(
            'user__notification', filter=Q(
                user__notification__code=code
            )
        )
    ).filter(notification_cnt=0).values_list('id', flat=True)

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
        'We noticed you haven\'t booked an appointment '
        'for {0} weeks. Tap too book now.'
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
