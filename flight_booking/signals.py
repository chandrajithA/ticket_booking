from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import FlightTrip, FlightSeatAvailability
from .seat_utils import update_available_seats, update_trip_base_price

def get_default_price(seat):
    base = 3000

    if seat.seat_class == 'business':
        base += 1500
    elif seat.seat_class == 'first':
        base += 3000

    if seat.is_window:
        base += 500

    if seat.is_left_aisle or seat.is_right_aisle:
        base += 300

    return base



@receiver(post_save, sender=FlightTrip)
def create_trip_seats(sender, instance, created, **kwargs):
    if created:
        flight_seats = instance.schedule.flight.seats.all()

        seat_objects = []

        for seat in flight_seats:
            seat_objects.append(
                FlightSeatAvailability(
                    trip=instance,
                    seat=seat,
                    seat_price=get_default_price(seat)
                )
            )

        FlightSeatAvailability.objects.bulk_create(seat_objects)

        update_trip_base_price(instance)
        update_available_seats(instance)



@receiver(post_save, sender=FlightSeatAvailability)
def update_trip_on_save(sender, instance, **kwargs):
    update_available_seats(instance.trip)
    update_trip_base_price(instance.trip)


@receiver(post_delete, sender=FlightSeatAvailability)
def update_trip_on_delete(sender, instance, **kwargs):
    update_available_seats(instance.trip)
    update_trip_base_price(instance.trip)