from .models import MovieShowBookingSeat
from .constants import MOVIE_SERVICE_CHARGE, MOVIE_TAX_PERCENT

def calculate_booking_amount(booking):

    seats = MovieShowBookingSeat.objects.filter(booking=booking)

    total_seats = booking.total_persons

    total_ticket = sum(s.price for s in seats)
    total_charges = total_seats * MOVIE_SERVICE_CHARGE

    subtotal = total_ticket + total_charges
    tax = (subtotal * MOVIE_TAX_PERCENT) / 100

    total = subtotal + tax

    return {
        "ticket": total_ticket,
        "charges": total_charges,
        "tax": tax,
        "total": total
    }