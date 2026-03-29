from django.contrib import admin
from .models import *

admin.site.register(Airport)
admin.site.register(Airline)
admin.site.register(Terminal)
admin.site.register(Flight)
admin.site.register(FlightSeat)
admin.site.register(FlightSchedule)
admin.site.register(FlightTrip)
admin.site.register(FlightSeatAvailability)
admin.site.register(FlightBooking)
admin.site.register(Passenger)
admin.site.register(FlightBookingSeat)
admin.site.register(Payment)