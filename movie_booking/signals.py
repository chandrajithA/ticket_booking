from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import MovieShow, MovieShowSeatAvailability
from .seat_utils import update_available_seats

def get_default_price(seat):
    base = 100

    if seat.seat_class == 'second':
        base += 50
    elif seat.seat_class == 'first':
        base += 100

    return base



@receiver(post_save, sender=MovieShow)
def create_movie_seats(sender, instance, created, **kwargs):
    if created:
        show_seats = instance.screen.seats.all()

        seat_objects = []

        for seat in show_seats:
            seat_objects.append(
                MovieShowSeatAvailability(
                    show=instance,
                    seat=seat,
                    seat_price=get_default_price(seat)
                )
            )

        MovieShowSeatAvailability.objects.bulk_create(seat_objects)

        update_available_seats(instance)



@receiver(post_save, sender=MovieShowSeatAvailability)
def update_trip_on_save(sender, instance, **kwargs):
    update_available_seats(instance.show)


@receiver(post_delete, sender=MovieShowSeatAvailability)
def update_trip_on_delete(sender, instance, **kwargs):
    update_available_seats(instance.show)