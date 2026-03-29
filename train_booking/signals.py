from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TrainTrip, TrainSeatAvailability, TrainSeat


@receiver(post_save, sender=TrainTrip)
def create_seats_for_trip(sender, instance, created, **kwargs):
    if created:
        if not TrainSeatAvailability.objects.filter(trip=instance).exists():
            create_train_seat_availability(instance)


PRICE_ADDER = {
    'SL': 0,
    '3A': 400,
    '2A': 650,
    '1A': 1500,
    'CC': 700,
    'EC': 1700,
}


def create_train_seat_availability(trip):
    train = trip.schedule.train
    base_price = trip.starting_price

    seats = TrainSeat.objects.filter(coach__train=train).select_related('coach')

    seat_objects = []

    for seat in seats:
        addition = PRICE_ADDER.get(seat.coach.coach_type, 0)

        price = base_price + addition

        seat_objects.append(
            TrainSeatAvailability(
                trip=trip,
                seat=seat,
                seat_price=price,
                status='available'
            )
        )

    TrainSeatAvailability.objects.bulk_create(seat_objects)