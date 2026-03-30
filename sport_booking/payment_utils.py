from .models import SportsEventBookingSeat
from .constants import SPORT_TAX_PERCENT
from django.db.models import Sum

def calculate_booking_amount(booking):

    seat_count = SportsEventBookingSeat.objects.filter(booking=booking).count()
    
    total_price = booking.event.seat_price * seat_count

    total_ticket = total_price

    subtotal = total_price
    tax = (subtotal * SPORT_TAX_PERCENT) / 100

    total = subtotal + tax

    return {
        "ticket": total_ticket,
        "tax": tax,
        "total": total
    }