from .models import TrainSeatAvailability
from .constants import TRAIN_TAX_PERCENT

def calculate_booking_amount(booking):

    seat = TrainSeatAvailability.objects.filter(trip=booking.trip, seat__coach__coach_type=booking.coach_type).first()
    seat_price = seat.seat_price
    total_passengers = booking.total_passengers

    total_ticket = seat_price * total_passengers

    subtotal = total_ticket
    tax = (subtotal * TRAIN_TAX_PERCENT) / 100

    total = subtotal + tax

    return {
        "ticket": total_ticket,
        "tax": tax,
        "total": total
    }