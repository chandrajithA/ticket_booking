from django.contrib import admin
from .models import *

admin.site.register(City)
admin.site.register(Theatre)
admin.site.register(Screen)
admin.site.register(Movie)
admin.site.register(ShowSeat)
admin.site.register(MovieShow)
admin.site.register(MovieShowSeatAvailability)
admin.site.register(MovieShowBooking)
admin.site.register(MovieShowBookingSeat)
admin.site.register(Payment)