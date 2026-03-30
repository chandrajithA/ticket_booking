from django.contrib import admin
from .models import *

admin.site.register(City)
admin.site.register(Stadium)
admin.site.register(Sport)
admin.site.register(StadiumSeat)
admin.site.register(SportsEvent)
admin.site.register(SportsEventSeatAvailability)
admin.site.register(SportsEventBooking)
admin.site.register(SportsEventBookingSeat)
admin.site.register(Payment)