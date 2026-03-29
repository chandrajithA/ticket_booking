from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import BusTrip, BusSeatAvailability
from .seat_utils import update_available_seats, update_trip_base_price

def get_default_price(seat):
    base = 800

    if seat.seat_class == 'lowerberth':
        base += 700
    elif seat.seat_class == 'upperbirth':
        base += 300

    if seat.is_single_one:
        base += 500

    return base



@receiver(post_save, sender=BusTrip)
def create_trip_seats(sender, instance, created, **kwargs):
    if created:
        bus_seats = instance.schedule.bus.seats.all()

        seat_objects = []

        for seat in bus_seats:
            seat_objects.append(
                BusSeatAvailability(
                    trip=instance,
                    seat=seat,
                    seat_price=get_default_price(seat)
                )
            )

        BusSeatAvailability.objects.bulk_create(seat_objects)

        update_trip_base_price(instance)
        update_available_seats(instance)



@receiver(post_save, sender=BusSeatAvailability)
def update_trip_on_save(sender, instance, **kwargs):
    update_available_seats(instance.trip)
    update_trip_base_price(instance.trip)


@receiver(post_delete, sender=BusSeatAvailability)
def update_trip_on_delete(sender, instance, **kwargs):
    update_available_seats(instance.trip)
    update_trip_base_price(instance.trip)