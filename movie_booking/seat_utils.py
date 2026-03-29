from .models import MovieShowSeatAvailability


def update_available_seats(show):
    count = MovieShowSeatAvailability.objects.filter(
        show=show,
        is_booked=False,
    ).count()

    show.available_seats = count
    show.save(update_fields=['available_seats'])