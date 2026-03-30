from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Event, EventSeatAvailability, Stadium, StadiumSeat


@receiver(post_save, sender=Stadium)
def create_stadium_seats(sender, instance, created, **kwargs):
    if created and instance.seats_count:
        if not StadiumSeat.objects.filter(stadium=instance).exists():
            create_seats(instance)


def create_seats(stadium):
    total_seats = stadium.seats_count

    seat_objects = []

    for i in range(1, total_seats + 1):
        seat_objects.append(
            StadiumSeat(
                stadium=stadium,
                seat_number=str(i)   # 👉 "1", "2", "3"
            )
        )

    StadiumSeat.objects.bulk_create(seat_objects)




@receiver(post_save, sender=Event)
def create_seats_for_sportevent(sender, instance, created, **kwargs):
    if created:
        if not EventSeatAvailability.objects.filter(event=instance).exists():
            create_sport_event_seat_availability(instance)



def create_sport_event_seat_availability(event):
    stadium = event.stadium

    # Get all seats of that stadium
    stadium_seats = StadiumSeat.objects.filter(stadium=stadium)

    seat_objects = []

    for seat in stadium_seats:
        seat_objects.append(
            EventSeatAvailability(
                event=event,
                seat=seat,
                status='available'
            )
        )

    # Bulk create for performance
    EventSeatAvailability.objects.bulk_create(seat_objects)

    