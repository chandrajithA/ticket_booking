from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Event, EventSeatAvailability


@receiver(post_save, sender=Event)
def create_seats_for_event(sender, instance, created, **kwargs):
    if created:
        if instance.seats_count and not EventSeatAvailability.objects.filter(event=instance).exists():
            create_event_seats(instance)



def create_event_seats(event):

    total_seats = event.seats_count

    seat_objects = []

    for i in range(1, total_seats + 1):
        seat_objects.append(
            EventSeatAvailability(
                event=event,
                seat_number=i,   # ✅ store directly here
                status='available'
            )
        )

    EventSeatAvailability.objects.bulk_create(seat_objects)



    