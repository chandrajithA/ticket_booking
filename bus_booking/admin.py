from django.contrib import admin
from .models import *

admin.site.register(BusStand)
admin.site.register(Travel)
admin.site.register(Terminal)
admin.site.register(Bus)
admin.site.register(BusSeat)
admin.site.register(BusSchedule)
admin.site.register(BusTrip)
admin.site.register(BusSeatAvailability)
admin.site.register(BusBooking)
admin.site.register(Passenger)
admin.site.register(BusBookingSeat)
admin.site.register(Payment)