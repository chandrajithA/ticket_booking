from .models import BusBookingSeat

def calculate_booking_amount(booking):

    seats = BusBookingSeat.objects.filter(passenger__booking=booking)

    total_ticket = sum(s.price for s in seats)

    subtotal = total_ticket
    tax = (subtotal * 5) / 100

    total = subtotal + tax

    return {
        "ticket": total_ticket,
        "tax": tax,
        "total": total
    }