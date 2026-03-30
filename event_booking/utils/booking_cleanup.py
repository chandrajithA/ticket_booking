from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from event_booking.models import EventBooking, EventSeatAvailability, EventBookingSeat, Payment


def clean_expired_bookings():

    expiry_time = timezone.now() - timedelta(minutes=15)

    EventBooking.objects.filter(
        status='pending',
        expires_at__lt=timezone.now(),
    ).update(status='cancelled',cancelled_at = timezone.now())

    # unlock expired seats
    EventSeatAvailability.objects.filter(
        status='locked',
        locked_at__lt=expiry_time,
        is_booked = False,
    ).update(
        status='available',
        locked_by=None,
        locked_at=None
    )

    # 🧹 delete seat mappings
    EventBookingSeat.objects.filter(
        booking__status='cancelled'
    ).delete()

    Payment.objects.filter(
        booking__status='cancelled',
        payment_status='pending',
    ).update(
        payment_status = 'cancelled',
        error_description = 'Payment cancelled',
    )




def run_cleanup_once():
    # run only once every 3 min
    lock = cache.add('cleanup_lock', True, timeout=180)

    if not lock:
        return

    clean_expired_bookings()