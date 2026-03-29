from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from train_booking.models import TrainBooking, TrainSeatAvailability, TrainBookingSeat, Payment


def clean_expired_bookings():

    expiry_time = timezone.now() - timedelta(minutes=15)

    TrainBooking.objects.filter(
        status='pending',
        expires_at__lt=timezone.now(),
    ).update(status='cancelled',cancelled_at = timezone.now())

    # 🧹 delete seat mappings
    TrainBookingSeat.objects.filter(
        passenger__booking__status='cancelled'
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