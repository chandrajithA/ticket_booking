from django.db.models import Min
from .models import FlightSeatAvailability

def update_trip_base_price(trip):
    min_price = FlightSeatAvailability.objects.filter(
        trip=trip,
        status='available'
    ).aggregate(min_price=Min('seat_price'))['min_price']

    trip.base_price = min_price or 0
    trip.save(update_fields=['base_price'])




def update_available_seats(trip):
    count = FlightSeatAvailability.objects.filter(
        trip=trip,
        is_booked=False,
    ).count()

    trip.available_seats = count
    trip.save(update_fields=['available_seats'])