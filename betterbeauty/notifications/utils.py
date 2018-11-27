import datetime
from io import TextIOBase
from typing import Dict, List, Tuple

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from appointment.models import Appointment
from appointment.types import AppointmentStatus
from client.models import Client
from core.models import UserRole
from salon.models import PreferredStylist, Stylist
from salon.utils import has_bookable_slots_with_discounts
from .models import Notification
from .types import NotificationChannel, NotificationCode


@transaction.atomic()
def send_all_push_notifications(stdout: TextIOBase, dry_run: bool=True) -> Tuple[int, int]:
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
        channel=NotificationChannel.PUSH
    ).select_for_update(skip_locked=True)
    for notification in pending_notifications.iterator():
        stdout.write('Going to send {0}'.format(notification.__str__()))
        if not dry_run:
            result = notification.send_and_mark_sent_push_notification_now()
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
        client_has_registered_devices,
        client__appointment__isnull=True,
        notification_cnt=0,
        stylist__services__is_enabled=True,
        stylist__user__phone__isnull=False,
        stylist__user__is_active=True,
        client__user__is_active=True,
        stylist__has_business_hours_set=True,
        stylist__deactivated_at=None,
    ).values_list('id', flat=True)
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
                channel=NotificationChannel.PUSH, message=message,
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
    :param dry_run: if set to False, no sending will actually occur
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
        client_has_registered_devices,
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
    eligible_clients = Client.objects.filter(
        id__in=eligible_clients_ids
    ).select_for_update(skip_locked=True)

    notifications_to_create_list: List[Notification] = []
    for client in eligible_clients.iterator():
        notifications_to_create_list.append(Notification(
            user=client.user, target=target, code=code,
            channel=NotificationChannel.PUSH, message=message,
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
    :param dry_run: if set to False, no sending will actually occur
    :param dry_run: if set to True, don't actually create notifications
    :return: number of notifications created
    """
    code = NotificationCode.HINT_TO_REBOOK
    send_time_window_start = datetime.time(19, 0)
    send_time_window_end = datetime.time(21, 0)
    discard_after = timezone.now() + datetime.timedelta(days=30)
    cutoff_datetime = timezone.now() - datetime.timedelta(days=32)
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
        client_has_registered_devices,
        created_at__gte=cutoff_datetime,
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
            channel=NotificationChannel.PUSH, message=message,
            discard_after=discard_after,
            send_time_window_start=send_time_window_start,
            send_time_window_end=send_time_window_end,
        ))
    # if any notifications were generated - bulk created them
    if notifications_to_create_list and not dry_run:
        Notification.objects.bulk_create(notifications_to_create_list)
    return len(notifications_to_create_list)
