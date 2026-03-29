from .models import FlightBookingSeat

def calculate_booking_amount(booking):

    seats = FlightBookingSeat.objects.filter(passenger__booking=booking)

    total_ticket = sum(s.price for s in seats)
    total_food = sum(s.food_price for s in seats)
    total_luggage = sum(s.luggage_price for s in seats)

    subtotal = total_ticket + total_food + total_luggage
    tax = (subtotal * 5) / 100

    total = subtotal + tax

    return {
        "ticket": total_ticket,
        "food": total_food,
        "luggage": total_luggage,
        "tax": tax,
        "total": total
    }